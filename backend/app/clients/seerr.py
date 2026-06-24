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

    async def mark_unavailable(self, media_id: int, *, confirm: bool = False) -> None:
        if not confirm:
            raise RuntimeError("Seerr mark_unavailable requires explicit confirm=True after dry-run.")
        raise NotImplementedError(
            f"{self.kind} unavailable mutation is blocked until the exact endpoint is verified "
            "against the configured service version."
        )
