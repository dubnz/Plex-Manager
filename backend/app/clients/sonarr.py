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

    async def list_episode_files(self, series_id: int) -> list[dict[str, Any]]:
        # Per-file detail (id, path, quality, size) for a series.
        # https://sonarr.tv/docs/api/#/EpisodeFile/get_api_v3_episodefile
        response = await self.request("GET", "/api/v3/episodefile", params={"seriesId": str(series_id)})
        return response.json()

    async def list_episodes(self, series_id: int) -> list[dict[str, Any]]:
        # Episode list with season/episode numbers, monitored state, episodeFileId.
        # https://sonarr.tv/docs/api/#/Episode/get_api_v3_episode
        response = await self.request("GET", "/api/v3/episode", params={"seriesId": str(series_id)})
        return response.json()

    async def delete_episode_file(self, episode_file_id: int, *, confirm: bool = False) -> None:
        if not confirm:
            raise RuntimeError("Sonarr delete_episode_file requires an explicit confirm=True call after dry-run.")
        # Deletes a single episode file from disk, leaving the series intact.
        # https://sonarr.tv/docs/api/#/EpisodeFile/delete_api_v3_episodefile__id_
        await self.request("DELETE", f"/api/v3/episodefile/{episode_file_id}")

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

