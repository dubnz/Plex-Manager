from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.models import ServiceConfigResponse, ServiceConfigUpdate


SECRET_KEYS = {
    "PLEX_TOKEN",
    "TAUTULLI_API_KEY",
    "SONARR_API_KEY",
    "RADARR_API_KEY",
    "SEERR_API_KEY",
    "LEGACY_SEERR_API_KEY",
}


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    return lowered in {"replace-me", "demo-token"} or lowered.startswith("demo-")


def public_config(settings: Settings) -> ServiceConfigResponse:
    return ServiceConfigResponse(
        plex_url=settings.plex_url,
        plex_token_set=bool(settings.plex_token),
        plex_token_placeholder=is_placeholder(settings.plex_token),
        plex_library_names=list(settings.plex_library_names),
        tautulli_url=settings.tautulli_url,
        tautulli_api_key_set=bool(settings.tautulli_api_key),
        tautulli_api_key_placeholder=is_placeholder(settings.tautulli_api_key),
        sonarr_url=settings.sonarr_url,
        sonarr_api_key_set=bool(settings.sonarr_api_key),
        sonarr_api_key_placeholder=is_placeholder(settings.sonarr_api_key),
        radarr_url=settings.radarr_url,
        radarr_api_key_set=bool(settings.radarr_api_key),
        radarr_api_key_placeholder=is_placeholder(settings.radarr_api_key),
        seerr_kind=settings.seerr_kind,
        seerr_url=settings.seerr_url,
        seerr_api_key_set=bool(settings.seerr_api_key),
        seerr_api_key_placeholder=is_placeholder(settings.seerr_api_key),
        legacy_seerr_url=settings.legacy_seerr_url,
        legacy_seerr_api_key_set=bool(settings.legacy_seerr_api_key),
        legacy_seerr_api_key_placeholder=is_placeholder(settings.legacy_seerr_api_key),
        sync_interval_minutes=settings.sync_interval_minutes,
        config_path=str(settings.config_path),
    )


def save_config(settings: Settings, update: ServiceConfigUpdate) -> None:
    existing = _read_config(settings.config_path)

    def secret(key: str, submitted: str | None, current: str) -> str:
        if submitted is None or submitted == "":
            return str(existing.get(key, current))
        return submitted

    # Start from existing config so deployment-specific keys not managed by the
    # settings form (e.g. LOCAL_MEDIA_PATHS, PROTECTED_MEDIA_PATHS) are preserved.
    payload = dict(existing)
    payload.update({
        "PLEX_URL": update.plex_url.rstrip("/"),
        "PLEX_TOKEN": secret("PLEX_TOKEN", update.plex_token, settings.plex_token),
        "PLEX_LIBRARY_NAMES": ",".join(update.plex_library_names),
        "TAUTULLI_URL": update.tautulli_url.rstrip("/"),
        "TAUTULLI_API_KEY": secret("TAUTULLI_API_KEY", update.tautulli_api_key, settings.tautulli_api_key),
        "SONARR_URL": update.sonarr_url.rstrip("/"),
        "SONARR_API_KEY": secret("SONARR_API_KEY", update.sonarr_api_key, settings.sonarr_api_key),
        "RADARR_URL": update.radarr_url.rstrip("/"),
        "RADARR_API_KEY": secret("RADARR_API_KEY", update.radarr_api_key, settings.radarr_api_key),
        "SEERR_KIND": update.seerr_kind,
        "SEERR_URL": update.seerr_url.rstrip("/"),
        "SEERR_API_KEY": secret("SEERR_API_KEY", update.seerr_api_key, settings.seerr_api_key),
        "LEGACY_SEERR_URL": update.legacy_seerr_url.rstrip("/"),
        "LEGACY_SEERR_API_KEY": secret(
            "LEGACY_SEERR_API_KEY",
            update.legacy_seerr_api_key,
            settings.legacy_seerr_api_key,
        ),
        "SYNC_INTERVAL_MINUTES": str(update.sync_interval_minutes),
    })

    settings.config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = settings.config_path.with_suffix(settings.config_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(settings.config_path)
    settings.config_path.chmod(0o600)


def _read_config(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}
