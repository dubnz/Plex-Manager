from __future__ import annotations

from app.core.config import Settings
from app.models import IntegrationStatus
from app.services.configuration import is_placeholder


def build_integration_status(settings: Settings) -> list[IntegrationStatus]:
    if settings.demo_mode:
        state = "demo"
        detail = "Demo data mode; no external request will be made."
        return [
            IntegrationStatus(name="Plex", state=state, detail=detail),
            IntegrationStatus(name="Tautulli", state=state, detail=detail),
            IntegrationStatus(name="Sonarr", state=state, detail=detail),
            IntegrationStatus(name="Radarr", state=state, detail=detail),
            IntegrationStatus(name="Seerr", state=state, detail=f"{detail} Kind: {settings.seerr_kind}."),
        ]

    statuses = [
        _status("Plex", settings.plex_token, "Plex token"),
        _status("Tautulli", settings.tautulli_api_key, "Tautulli API key"),
        _status("Sonarr", settings.sonarr_api_key, "Sonarr API key"),
        _status("Radarr", settings.radarr_api_key, "Radarr API key"),
        _status("Seerr", settings.seerr_api_key, f"Seerr API key. Kind: {settings.seerr_kind}"),
    ]
    if settings.legacy_seerr_url or not is_placeholder(settings.legacy_seerr_api_key):
        statuses.append(_status("Legacy Overseerr", settings.legacy_seerr_api_key, "Legacy Overseerr API key"))
    return statuses


def _status(name: str, secret: str, label: str) -> IntegrationStatus:
    if is_placeholder(secret):
        return IntegrationStatus(name=name, state="missing", detail=f"{label} is not configured.")
    return IntegrationStatus(
        name=name,
        state="blocked",
        detail="Configured, but read-only auth verification has not been run in this session.",
    )
