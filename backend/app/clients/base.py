from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class ApiClientError(RuntimeError):
    """Raised when an external API call fails after retries."""


class HttpApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
        max_attempts: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.max_attempts = max_attempts

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        last_error: Exception | None = None
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                    response = await client.request(method, url, params=params, json=json)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
                    await asyncio.sleep(0.35 * attempt)
                    continue
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    await asyncio.sleep(0.35 * attempt)
                    continue
        raise ApiClientError(f"{method} {url} failed after {self.max_attempts} attempts: {last_error}")

    @staticmethod
    def page_window(total: int, page_size: int) -> list[tuple[int, int]]:
        return [(start, min(page_size, total - start)) for start in range(0, total, page_size)]

