from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_KEYS = (
    "PLEX_URL",
    "PLEX_TOKEN",
    "TAUTULLI_URL",
    "TAUTULLI_API_KEY",
    "SONARR_URL",
    "SONARR_API_KEY",
    "RADARR_URL",
    "RADARR_API_KEY",
    "SEERR_KIND",
    "SEERR_URL",
    "SEERR_API_KEY",
)


class ConfigurationError(RuntimeError):
    """Raised when production startup would be unsafe."""


@dataclass(frozen=True)
class Settings:
    demo_mode: bool
    plex_url: str
    plex_token: str
    plex_library_names: tuple[str, ...]
    tautulli_url: str
    tautulli_api_key: str
    sonarr_url: str
    sonarr_api_key: str
    radarr_url: str
    radarr_api_key: str
    seerr_kind: str
    seerr_url: str
    seerr_api_key: str
    db_path: Path
    sync_interval_minutes: int


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _split_libraries(value: str | None) -> tuple[str, ...]:
    raw = value or "Movies,TV Shows"
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_settings() -> Settings:
    load_dotenv()

    demo_mode = _truthy(os.getenv("PLEX_MANAGER_DEMO_MODE"))
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing and not demo_mode:
        raise ConfigurationError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set PLEX_MANAGER_DEMO_MODE=true only for local demo data."
        )

    seerr_kind = (os.getenv("SEERR_KIND") or "").strip().lower()
    if not demo_mode and seerr_kind not in {"overseerr", "jellyseerr"}:
        raise ConfigurationError("SEERR_KIND must be exactly 'overseerr' or 'jellyseerr'.")

    return Settings(
        demo_mode=demo_mode,
        plex_url=os.getenv("PLEX_URL", "http://demo-plex.local:32400").rstrip("/"),
        plex_token=os.getenv("PLEX_TOKEN", "demo-token"),
        plex_library_names=_split_libraries(os.getenv("PLEX_LIBRARY_NAMES")),
        tautulli_url=os.getenv("TAUTULLI_URL", "http://demo-tautulli.local:8181").rstrip("/"),
        tautulli_api_key=os.getenv("TAUTULLI_API_KEY", "demo-tautulli-key"),
        sonarr_url=os.getenv("SONARR_URL", "http://demo-sonarr.local:8989").rstrip("/"),
        sonarr_api_key=os.getenv("SONARR_API_KEY", "demo-sonarr-key"),
        radarr_url=os.getenv("RADARR_URL", "http://demo-radarr.local:7878").rstrip("/"),
        radarr_api_key=os.getenv("RADARR_API_KEY", "demo-radarr-key"),
        seerr_kind=seerr_kind or "demo",
        seerr_url=os.getenv("SEERR_URL", "http://demo-seerr.local:5055").rstrip("/"),
        seerr_api_key=os.getenv("SEERR_API_KEY", "demo-seerr-key"),
        db_path=Path(os.getenv("DB_PATH", "data/plex-manager.db")),
        sync_interval_minutes=int(os.getenv("SYNC_INTERVAL_MINUTES", "60")),
    )

