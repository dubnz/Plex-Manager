from __future__ import annotations

from typing import Any

from app.clients.base import HttpApiClient


class SonarrClient(HttpApiClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url, headers={"X-Api-Key": api_key})

    async def list_series(self) -> list[dict[str, Any]]:
        # Official docs fetched 2026-06-22:
        # https://sonarr.tv/docs/api/
        response = await self.request("GET", "/api/v3/series")
        return response.json()

    async def delete_series(
        self,
        series_id: int,
        *,
        delete_files: bool,
        add_import_list_exclusion: bool = False,
        confirm: bool = False,
    ) -> None:
        if not confirm:
            raise RuntimeError("Sonarr delete_series requires an explicit confirm=True call after dry-run.")
        # Official docs fetched 2026-06-22:
        # https://sonarr.tv/docs/api/
        await self.request(
            "DELETE",
            f"/api/v3/series/{series_id}",
            params={
                "deleteFiles": str(delete_files).lower(),
                "addImportListExclusion": str(add_import_list_exclusion).lower(),
            },
        )

