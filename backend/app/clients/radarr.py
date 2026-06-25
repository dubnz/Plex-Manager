from __future__ import annotations

from typing import Any

from app.clients.base import HttpApiClient


class RadarrClient(HttpApiClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url, headers={"X-Api-Key": api_key})

    async def list_movies(self) -> list[dict[str, Any]]:
        # Official docs fetched 2026-06-22:
        # https://radarr.video/docs/api/
        response = await self.request("GET", "/api/v3/movie")
        return response.json()

    async def list_movie_files(self, movie_id: int) -> list[dict[str, Any]]:
        # Per-file detail (id, path, quality, size) for a movie.
        # https://radarr.video/docs/api/#/MovieFile/get_api_v3_moviefile
        response = await self.request("GET", "/api/v3/moviefile", params={"movieId": str(movie_id)})
        return response.json()

    async def delete_movie_file(self, movie_file_id: int, *, confirm: bool = False) -> None:
        if not confirm:
            raise RuntimeError("Radarr delete_movie_file requires an explicit confirm=True call after dry-run.")
        # Deletes a single movie file from disk, leaving the movie entry intact.
        # https://radarr.video/docs/api/#/MovieFile/delete_api_v3_moviefile__id_
        await self.request("DELETE", f"/api/v3/moviefile/{movie_file_id}")

    async def delete_movie(
        self,
        movie_id: int,
        *,
        delete_files: bool,
        add_import_exclusion: bool = False,
        confirm: bool = False,
    ) -> None:
        if not confirm:
            raise RuntimeError("Radarr delete_movie requires an explicit confirm=True call after dry-run.")
        # Official docs fetched 2026-06-22:
        # https://radarr.video/docs/api/
        await self.request(
            "DELETE",
            f"/api/v3/movie/{movie_id}",
            params={
                "deleteFiles": str(delete_files).lower(),
                "addImportExclusion": str(add_import_exclusion).lower(),
            },
        )

