from __future__ import annotations

from typing import Any

from app.clients.base import HttpApiClient


class TautulliClient(HttpApiClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url)
        self.api_key = api_key

    async def get_history(self, *, start: int = 0, length: int = 100) -> list[dict[str, Any]]:
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
        return data.get("data", []) if isinstance(data, dict) else []

