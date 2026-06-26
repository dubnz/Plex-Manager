from __future__ import annotations

from typing import Any, Literal

from app.clients.base import HttpApiClient


SeerrKind = Literal["overseerr", "jellyseerr"]


class SeerrClient(HttpApiClient):
    def __init__(self, base_url: str, api_key: str, kind: SeerrKind) -> None:
        super().__init__(base_url, headers={"X-Api-Key": api_key})
        self.kind = kind

    async def list_requests(self, *, take: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        # Official docs fetched 2026-06-22:
        # Overseerr: https://api-docs.overseerr.dev/
        # Jellyseerr/Seerr: https://docs.seerr.dev/api/seerr-api/
        response = await self.request("GET", "/api/v1/request", params={"take": take, "skip": skip})
        payload = response.json()
        results = payload.get("results")
        return results if isinstance(results, list) else []

    async def list_all_requests(self, *, page_size: int = 100, max_pages: int = 100) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        skip = 0
        for _ in range(max_pages):
            page = await self.list_requests(take=page_size, skip=skip)
            requests.extend(page)
            if len(page) < page_size:
                break
            skip += len(page)
        return requests

    async def list_media(self, *, take: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        # https://api-docs.overseerr.dev/#/media/get_media
        response = await self.request("GET", "/api/v1/media", params={"take": take, "skip": skip})
        results = response.json().get("results")
        return results if isinstance(results, list) else []

    async def media_id_by_rating_key(self, *, page_size: int = 100, max_pages: int = 200) -> dict[str, int]:
        """Map Plex ratingKey -> Seerr internal media id, used to resolve which
        media record to clear after a delete. ratingKey is reliably populated on
        available media (verified against Jellyseerr 3.3.0)."""
        mapping: dict[str, int] = {}
        skip = 0
        for _ in range(max_pages):
            page = await self.list_media(take=page_size, skip=skip)
            for record in page:
                rating_key = record.get("ratingKey")
                media_id = record.get("id")
                if rating_key is not None and media_id is not None:
                    mapping[str(rating_key)] = int(media_id)
            if len(page) < page_size:
                break
            skip += len(page)
        return mapping

    async def mark_unavailable(self, media_id: int, *, confirm: bool = False) -> None:
        if not confirm:
            raise RuntimeError("Seerr mark_unavailable requires explicit confirm=True.")
        # Removes the media availability record so the title shows as unavailable
        # and can be re-requested. Verified against Jellyseerr 3.3.0: returns 204,
        # idempotent. https://api-docs.overseerr.dev/#/media/deleteMedia
        await self.request("DELETE", f"/api/v1/media/{media_id}")
