from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

from app.clients.base import HttpApiClient


@dataclass(frozen=True)
class PlexLibrarySection:
    key: str
    title: str
    type: str


@dataclass(frozen=True)
class PlexMediaSummary:
    rating_key: str
    title: str
    media_type: str
    year: int | None
    added_at: datetime
    thumb: str | None
    file_size_bytes: int
    guids: tuple[str, ...] = ()
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    imdb_id: str | None = None
    play_count: int = 0
    last_played: datetime | None = None


class PlexClient(HttpApiClient):
    def __init__(self, base_url: str, token: str) -> None:
        super().__init__(base_url)
        self.token = token

    async def list_libraries(self) -> list[PlexLibrarySection]:
        # Official docs fetched 2026-06-22:
        # https://developer.plex.tv/docs/api-reference/library/get-all-libraries
        response = await self.request("GET", "/library/sections", params={"X-Plex-Token": self.token})
        root = ElementTree.fromstring(response.text)
        return [
            PlexLibrarySection(
                key=directory.attrib["key"],
                title=directory.attrib["title"],
                type=directory.attrib.get("type", "unknown"),
            )
            for directory in root.findall("Directory")
        ]

    async def list_items(self, section_key: str) -> list[PlexMediaSummary]:
        # Official docs fetched 2026-06-22:
        # https://developer.plex.tv/docs/api-reference/library/get-library-items
        response = await self.request(
            "GET",
            f"/library/sections/{section_key}/all",
            params={"X-Plex-Token": self.token, "includeGuids": "1"},
        )
        root = ElementTree.fromstring(response.text)
        return [self._parse_media_node(node) for node in root if node.tag in {"Video", "Directory"}]

    async def refresh_library_section(self, section_key: str) -> None:
        # Official docs fetched 2026-06-22:
        # https://developer.plex.tv/docs/api-reference/library/refresh-library
        await self.request(
            "GET",
            f"/library/sections/{section_key}/refresh",
            params={"X-Plex-Token": self.token},
        )

    def _parse_media_node(self, node: ElementTree.Element) -> PlexMediaSummary:
        added_at = _int_or_zero(node.attrib.get("addedAt"))
        guids = _node_guids(node)
        external_ids = _external_ids_from_guids(guids)
        return PlexMediaSummary(
            rating_key=node.attrib["ratingKey"],
            title=node.attrib.get("title", "Untitled"),
            media_type=node.attrib.get("type", "unknown"),
            year=int(node.attrib["year"]) if node.attrib.get("year") else None,
            added_at=datetime.fromtimestamp(added_at, UTC),
            thumb=node.attrib.get("thumb"),
            file_size_bytes=_media_size(node),
            guids=guids,
            tmdb_id=external_ids.get("tmdb"),
            tvdb_id=external_ids.get("tvdb"),
            imdb_id=external_ids.get("imdb"),
            play_count=_int_or_zero(node.attrib.get("viewCount") or node.attrib.get("viewedLeafCount")),
            last_played=_timestamp_to_datetime(node.attrib.get("lastViewedAt")),
        )


def _node_guids(node: ElementTree.Element) -> tuple[str, ...]:
    values = [node.attrib["guid"]] if node.attrib.get("guid") else []
    values.extend(guid.attrib["id"] for guid in node.findall("./Guid") if guid.attrib.get("id"))
    return tuple(dict.fromkeys(values))


def _external_ids_from_guids(guids: tuple[str, ...]) -> dict[str, Any]:
    ids: dict[str, Any] = {}
    for guid in guids:
        lowered = guid.lower()
        value = guid.rsplit("/", 1)[-1].split("?", 1)[0]
        if "imdb://" in lowered and value.startswith("tt"):
            ids.setdefault("imdb", value)
        elif "tmdb://" in lowered or "themoviedb://" in lowered:
            if parsed := _int_or_none(value):
                ids.setdefault("tmdb", parsed)
        elif "tvdb://" in lowered or "thetvdb://" in lowered:
            if parsed := _int_or_none(value):
                ids.setdefault("tvdb", parsed)
    return ids


def _media_size(node: ElementTree.Element) -> int:
    part_size = sum(_int_or_zero(part.attrib.get("size")) for part in node.findall(".//Part"))
    if part_size:
        return part_size
    return sum(_int_or_zero(media.attrib.get("size")) for media in node.findall(".//Media"))


def _timestamp_to_datetime(value: str | None) -> datetime | None:
    timestamp = _int_or_none(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC)


def _int_or_zero(value: str | None) -> int:
    return _int_or_none(value) or 0


def _int_or_none(value: str | None) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
