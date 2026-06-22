from __future__ import annotations

from app.core.config import Settings
from app.models import IntegrationStatus


def build_integration_status(settings: Settings) -> list[IntegrationStatus]:
    if settings.demo_mode:
        state = "demo"
        detail = "Demo data mode; no external request will be made."
    else:
        state = "blocked"
        detail = "Configured, but read-only auth verification has not been run in this session."

    return [
        IntegrationStatus(name="Plex", state=state, detail=detail),
        IntegrationStatus(name="Tautulli", state=state, detail=detail),
        IntegrationStatus(name="Sonarr", state=state, detail=detail),
        IntegrationStatus(name="Radarr", state=state, detail=detail),
        IntegrationStatus(name="Seerr", state=state, detail=f"{detail} Kind: {settings.seerr_kind}."),
    ]

