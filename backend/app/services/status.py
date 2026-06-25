from __future__ import annotations

import time

from app.core.config import Settings
from app.models import IntegrationStatus


# Short-lived cache so the frequently-polled /status endpoint reflects real
# connectivity without probing every external service on every request.
_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, object] = {"expires": 0.0, "value": None}


def invalidate_status_cache() -> None:
    _cache["expires"] = 0.0
    _cache["value"] = None


async def build_integration_status(settings: Settings) -> list[IntegrationStatus]:
    if settings.demo_mode:
        detail = "Demo data mode; no external request will be made."
        return [
            IntegrationStatus(name="Plex", state="demo", detail=detail),
            IntegrationStatus(name="Tautulli", state="demo", detail=detail),
            IntegrationStatus(name="Sonarr", state="demo", detail=detail),
            IntegrationStatus(name="Radarr", state="demo", detail=detail),
            IntegrationStatus(name="Seerr", state="demo", detail=f"{detail} Kind: {settings.seerr_kind}."),
        ]

    now = time.monotonic()
    cached = _cache["value"]
    if cached is not None and now < float(_cache["expires"]):
        return cached  # type: ignore[return-value]

    # Import here to avoid a circular import (validation imports clients/config).
    from app.services.validation import validate_connections

    result = await validate_connections(settings)
    _cache["value"] = result.integrations
    _cache["expires"] = now + _CACHE_TTL_SECONDS
    return result.integrations
