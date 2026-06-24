from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app import db
from app.clients.plex import PlexClient, PlexLibrarySection
from app.clients.radarr import RadarrClient
from app.clients.seerr import SeerrClient
from app.clients.sonarr import SonarrClient
from app.clients.tautulli import TautulliClient
from app.core.config import Settings
from app.models import SyncRunResponse
from app.services.configuration import is_placeholder


TITLE_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ManagerInfo:
    id: int
    file_size_bytes: int
    available: bool


@dataclass
class WatchStats:
    play_count: int = 0
    last_played: datetime | None = None
    watched_by: set[str] = field(default_factory=set)

    def record(self, *, played_at: datetime | None, user: str | None) -> None:
        self.play_count += 1
        if played_at and (self.last_played is None or played_at > self.last_played):
            self.last_played = played_at
        if user:
            self.watched_by.add(user)


@dataclass(frozen=True)
class RequestInfo:
    requested_by: str | None
    request_date: datetime | None


@dataclass
class RequestIndexes:
    by_rating_key: dict[str, RequestInfo] = field(default_factory=dict)
    by_manager: dict[tuple[str, int], RequestInfo] = field(default_factory=dict)

    def find(self, *, rating_key: str, manager_kind: str, manager_id: int | None) -> RequestInfo | None:
        if rating_key in self.by_rating_key:
            return self.by_rating_key[rating_key]
        if manager_id is not None and (manager_kind, manager_id) in self.by_manager:
            return self.by_manager[(manager_kind, manager_id)]
        return None


async def run_sync(settings: Settings, conn: sqlite3.Connection) -> SyncRunResponse:
    if settings.demo_mode:
        db.seed_demo_data(conn)
        return SyncRunResponse(status="demo", detail="Demo data is seeded.", synced_items=len(db.list_media(conn)))

    if is_placeholder(settings.plex_token):
        return SyncRunResponse(
            status="blocked",
            detail="Enter a real Plex token before running sync.",
            selected_libraries=list(settings.plex_library_names),
        )

    plex = PlexClient(settings.plex_url, settings.plex_token)
    sections = await plex.list_libraries()
    selected = _selected_sections(sections, settings.plex_library_names)
    if not selected:
        return SyncRunResponse(
            status="blocked",
            detail="None of the selected Plex library names were found on the Plex server.",
            selected_libraries=list(settings.plex_library_names),
        )

    radarr_movies = await _radarr_movie_info(settings)
    sonarr_series = await _sonarr_series_info(settings)
    watch_stats = await _tautulli_watch_stats(settings)
    request_indexes = await _seerr_request_indexes(settings)
    rows: list[dict] = []
    warnings: list[str] = []

    found_names = {section.title for section in selected}
    missing_names = sorted(set(settings.plex_library_names) - found_names)
    if missing_names:
        warnings.append(f"Selected libraries not found: {', '.join(missing_names)}")

    for section in selected:
        items = await plex.list_items(section.key)
        for item in items:
            media_type = "show" if section.type == "show" or item.media_type == "show" else "movie"
            manager_kind = "none"
            manager_id = None
            manager_info: ManagerInfo | None = None
            lookup_key = _media_lookup_key(item.title, item.year)
            if media_type == "movie" and lookup_key in radarr_movies:
                manager_info = radarr_movies[lookup_key]
                manager_kind = "radarr"
                manager_id = manager_info.id
            if media_type == "show" and lookup_key in sonarr_series:
                manager_info = sonarr_series[lookup_key]
                manager_kind = "sonarr"
                manager_id = manager_info.id

            stats = watch_stats.get(item.rating_key, WatchStats())
            request = request_indexes.find(
                rating_key=item.rating_key,
                manager_kind=manager_kind,
                manager_id=manager_id,
            )
            file_size_bytes = manager_info.file_size_bytes if manager_info and manager_info.file_size_bytes else item.file_size_bytes
            available = manager_info.available if manager_info else True

            rows.append(
                {
                    "plex_rating_key": item.rating_key,
                    "library": section.title,
                    "media_type": media_type,
                    "title": item.title,
                    "year": item.year,
                    "added_at": item.added_at.isoformat(),
                    "play_count": stats.play_count,
                    "last_played": stats.last_played.isoformat() if stats.last_played else None,
                    "watched_by": sorted(stats.watched_by, key=str.lower),
                    "requested_by": request.requested_by if request else None,
                    "request_date": request.request_date.isoformat() if request and request.request_date else None,
                    "manager_kind": manager_kind,
                    "manager_id": manager_id,
                    "available": available,
                    "file_size_bytes": file_size_bytes,
                }
            )

    db.upsert_media_items(conn, rows)
    return SyncRunResponse(
        status="ok",
        detail=f"Synced {len(rows)} Plex item(s) from selected libraries.",
        synced_items=len(rows),
        selected_libraries=[section.title for section in selected],
        warnings=warnings,
    )


def _selected_sections(
    sections: list[PlexLibrarySection],
    selected_names: tuple[str, ...],
) -> list[PlexLibrarySection]:
    selected = set(selected_names)
    return [section for section in sections if section.title in selected]


async def _radarr_movie_info(settings: Settings) -> dict[tuple[str, int | None], ManagerInfo]:
    if is_placeholder(settings.radarr_api_key):
        return {}
    try:
        movies = await RadarrClient(settings.radarr_url, settings.radarr_api_key).list_movies()
    except Exception:
        return {}
    return {
        _media_lookup_key(str(movie.get("title", "")), _int_or_none(movie.get("year"))): ManagerInfo(
            id=int(movie["id"]),
            file_size_bytes=_int_or_none(movie.get("sizeOnDisk")) or 0,
            available=bool(movie.get("hasFile") or movie.get("movieFileId") or movie.get("sizeOnDisk")),
        )
        for movie in movies
        if movie.get("title") and movie.get("id") is not None
    }


async def _sonarr_series_info(settings: Settings) -> dict[tuple[str, int | None], ManagerInfo]:
    if is_placeholder(settings.sonarr_api_key):
        return {}
    try:
        series = await SonarrClient(settings.sonarr_url, settings.sonarr_api_key).list_series()
    except Exception:
        return {}
    infos: dict[tuple[str, int | None], ManagerInfo] = {}
    for item in series:
        if not item.get("title") or item.get("id") is None:
            continue
        statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
        size_on_disk = _int_or_none(statistics.get("sizeOnDisk")) or 0
        episode_file_count = _int_or_none(statistics.get("episodeFileCount")) or 0
        infos[_media_lookup_key(str(item["title"]), _int_or_none(item.get("year")))] = ManagerInfo(
            id=int(item["id"]),
            file_size_bytes=size_on_disk,
            available=episode_file_count > 0 or size_on_disk > 0,
        )
    return infos


async def _tautulli_watch_stats(settings: Settings) -> dict[str, WatchStats]:
    if is_placeholder(settings.tautulli_api_key):
        return {}
    try:
        rows = await TautulliClient(settings.tautulli_url, settings.tautulli_api_key).get_all_history()
    except Exception:
        return {}
    return _watch_stats_from_history(rows)


def _watch_stats_from_history(rows: list[dict[str, Any]]) -> dict[str, WatchStats]:
    stats: dict[str, WatchStats] = {}
    for row in rows:
        rating_key = _history_rating_key(row)
        if not rating_key:
            continue
        stats.setdefault(rating_key, WatchStats()).record(
            played_at=_timestamp_to_datetime(row.get("date") or row.get("stopped") or row.get("started")),
            user=_watch_user(row),
        )
    return stats


def _history_rating_key(row: dict[str, Any]) -> str | None:
    media_type = str(row.get("media_type") or "").lower()
    if media_type == "episode":
        return _clean_string(row.get("grandparent_rating_key"))
    if media_type == "movie":
        return _clean_string(row.get("rating_key"))
    return _clean_string(row.get("grandparent_rating_key") or row.get("rating_key"))


def _watch_user(row: dict[str, Any]) -> str | None:
    return _clean_string(row.get("friendly_name")) or _clean_string(row.get("user"))


async def _seerr_request_indexes(settings: Settings) -> RequestIndexes:
    request_sources: list[list[dict[str, Any]]] = []
    if not is_placeholder(settings.seerr_api_key):
        try:
            request_sources.append(
                await SeerrClient(settings.seerr_url, settings.seerr_api_key, settings.seerr_kind).list_all_requests()
            )
        except Exception:
            pass
    if settings.legacy_seerr_url and not is_placeholder(settings.legacy_seerr_api_key):
        try:
            request_sources.append(
                await SeerrClient(
                    settings.legacy_seerr_url,
                    settings.legacy_seerr_api_key,
                    "overseerr",
                ).list_all_requests()
            )
        except Exception:
            pass
    return _request_indexes_from_sources(request_sources)


def _request_indexes_from_sources(request_sources: list[list[dict[str, Any]]]) -> RequestIndexes:
    indexes = RequestIndexes()
    for rows in request_sources:
        for row in rows:
            request = RequestInfo(
                requested_by=_requester_name(row),
                request_date=_parse_datetime(row.get("createdAt")),
            )
            if not request.requested_by:
                continue
            media = row.get("media") if isinstance(row.get("media"), dict) else {}
            rating_key = _clean_string(media.get("ratingKey"))
            if rating_key:
                indexes.by_rating_key.setdefault(rating_key, request)
            manager_kind = _request_manager_kind(row)
            manager_id = _int_or_none(media.get("externalServiceId"))
            if manager_kind and manager_id is not None:
                indexes.by_manager.setdefault((manager_kind, manager_id), request)
    return indexes


def _request_manager_kind(row: dict[str, Any]) -> str | None:
    request_type = str(row.get("type") or (row.get("media") or {}).get("mediaType") or "").lower()
    if request_type == "movie":
        return "radarr"
    if request_type == "tv":
        return "sonarr"
    return None


def _requester_name(row: dict[str, Any]) -> str | None:
    user = row.get("requestedBy") if isinstance(row.get("requestedBy"), dict) else {}
    for key in ("displayName", "plexUsername", "username"):
        if value := _clean_string(user.get(key)):
            return value
    if email := _clean_string(user.get("email")):
        return email.split("@", 1)[0]
    return None


def _media_lookup_key(title: str, year: int | None) -> tuple[str, int | None]:
    normalized = TITLE_KEY_PATTERN.sub(" ", title.lower()).strip()
    return normalized, year


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _timestamp_to_datetime(value: Any) -> datetime | None:
    timestamp = _int_or_none(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC)


def _parse_datetime(value: Any) -> datetime | None:
    raw = _clean_string(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
