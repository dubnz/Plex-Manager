from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
            params={"X-Plex-Token": self.token},
        )
        root = ElementTree.fromstring(response.text)
        return [self._parse_media_node(node) for node in root if node.tag in {"Video", "Directory"}]

    def _parse_media_node(self, node: ElementTree.Element) -> PlexMediaSummary:
        added_at = int(node.attrib.get("addedAt", "0") or "0")
        return PlexMediaSummary(
            rating_key=node.attrib["ratingKey"],
            title=node.attrib.get("title", "Untitled"),
            media_type=node.attrib.get("type", "unknown"),
            year=int(node.attrib["year"]) if node.attrib.get("year") else None,
            added_at=datetime.fromtimestamp(added_at, UTC),
            thumb=node.attrib.get("thumb"),
        )

