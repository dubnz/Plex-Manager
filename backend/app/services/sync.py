from __future__ import annotations

import sqlite3

from app import db
from app.clients.plex import PlexClient, PlexLibrarySection
from app.clients.radarr import RadarrClient
from app.clients.sonarr import SonarrClient
from app.core.config import Settings
from app.models import SyncRunResponse
from app.services.configuration import is_placeholder


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

    radarr_ids = await _radarr_movie_ids(settings)
    sonarr_ids = await _sonarr_series_ids(settings)
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
            lookup_key = (item.title.strip().lower(), item.year)
            if media_type == "movie" and lookup_key in radarr_ids:
                manager_kind = "radarr"
                manager_id = radarr_ids[lookup_key]
            if media_type == "show" and lookup_key in sonarr_ids:
                manager_kind = "sonarr"
                manager_id = sonarr_ids[lookup_key]

            rows.append(
                {
                    "plex_rating_key": item.rating_key,
                    "library": section.title,
                    "media_type": media_type,
                    "title": item.title,
                    "year": item.year,
                    "added_at": item.added_at.isoformat(),
                    "play_count": 0,
                    "last_played": None,
                    "watched_by": [],
                    "requested_by": None,
                    "request_date": None,
                    "manager_kind": manager_kind,
                    "manager_id": manager_id,
                    "available": True,
                    "file_size_bytes": 0,
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


async def _radarr_movie_ids(settings: Settings) -> dict[tuple[str, int | None], int]:
    if is_placeholder(settings.radarr_api_key):
        return {}
    try:
        movies = await RadarrClient(settings.radarr_url, settings.radarr_api_key).list_movies()
    except Exception:
        return {}
    return {
        (str(movie.get("title", "")).strip().lower(), movie.get("year")): int(movie["id"])
        for movie in movies
        if movie.get("title") and movie.get("id") is not None
    }


async def _sonarr_series_ids(settings: Settings) -> dict[tuple[str, int | None], int]:
    if is_placeholder(settings.sonarr_api_key):
        return {}
    try:
        series = await SonarrClient(settings.sonarr_url, settings.sonarr_api_key).list_series()
    except Exception:
        return {}
    return {
        (str(item.get("title", "")).strip().lower(), item.get("year")): int(item["id"])
        for item in series
        if item.get("title") and item.get("id") is not None
    }

