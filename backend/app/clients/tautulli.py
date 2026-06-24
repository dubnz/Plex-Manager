from __future__ import annotations

from typing import Any

from app.clients.base import HttpApiClient


class TautulliClient(HttpApiClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url)
        self.api_key = api_key

    async def get_history(self, *, start: int = 0, length: int = 100) -> list[dict[str, Any]]:
        page = await self.get_history_page(start=start, length=length)
        return page.rows

    async def get_all_history(self, *, page_size: int = 1000, max_pages: int = 25) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start = 0
        for _ in range(max_pages):
            page = await self.get_history_page(start=start, length=page_size)
            rows.extend(page.rows)
            start += len(page.rows)
            if not page.rows or start >= page.total:
                break
        return rows

    async def get_history_page(self, *, start: int = 0, length: int = 100) -> "TautulliHistoryPage":
        # Official docs fetched 2026-06-22:
        # https://github.com/Tautulli/Tautulli/wiki/Tautulli-API-Reference
        response = await self.request(
            "GET",
            "/api/v2",
            params={
                "apikey": self.api_key,
                "cmd": "get_history",
                "start": start,
                "length": length,
            },
        )
        payload = response.json()
        data = payload.get("response", {}).get("data", {})
        if not isinstance(data, dict):
            return TautulliHistoryPage(rows=[], total=0)
        rows = data.get("data", [])
        return TautulliHistoryPage(
            rows=rows if isinstance(rows, list) else [],
            total=int(data.get("recordsFiltered") or data.get("recordsTotal") or 0),
        )


class TautulliHistoryPage:
    def __init__(self, *, rows: list[dict[str, Any]], total: int) -> None:
        self.rows = rows
        self.total = total
