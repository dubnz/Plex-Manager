from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    legacy_seerr_url: str
    legacy_seerr_api_key: str
    db_path: Path
    config_path: Path
    sync_interval_minutes: int


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _split_libraries(value: str | None) -> tuple[str, ...]:
    raw = value or "Movies,TV Shows"
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _load_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError(f"{config_path} must contain a JSON object.")
    return payload


def load_settings() -> Settings:
    load_dotenv()

    db_path = Path(os.getenv("DB_PATH", "data/plex-manager.db"))
    config_path = Path(os.getenv("CONFIG_PATH", str(db_path.parent / "config.json")))
    file_config = _load_config_file(config_path)

    def value(key: str, default: str | None = None) -> str | None:
        raw = file_config.get(key, os.getenv(key, default))
        return str(raw) if raw is not None else None

    demo_mode = _truthy(os.getenv("PLEX_MANAGER_DEMO_MODE"))
    missing = [key for key in REQUIRED_KEYS if not value(key)]
    if missing and not demo_mode:
        raise ConfigurationError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set PLEX_MANAGER_DEMO_MODE=true only for local demo data."
        )

    seerr_kind = (value("SEERR_KIND") or "").strip().lower()
    if not demo_mode and seerr_kind not in {"overseerr", "jellyseerr"}:
        raise ConfigurationError("SEERR_KIND must be exactly 'overseerr' or 'jellyseerr'.")

    return Settings(
        demo_mode=demo_mode,
        plex_url=value("PLEX_URL", "http://demo-plex.local:32400").rstrip("/"),
        plex_token=value("PLEX_TOKEN", "demo-token"),
        plex_library_names=_split_libraries(value("PLEX_LIBRARY_NAMES")),
        tautulli_url=value("TAUTULLI_URL", "http://demo-tautulli.local:8181").rstrip("/"),
        tautulli_api_key=value("TAUTULLI_API_KEY", "demo-tautulli-key"),
        sonarr_url=value("SONARR_URL", "http://demo-sonarr.local:8989").rstrip("/"),
        sonarr_api_key=value("SONARR_API_KEY", "demo-sonarr-key"),
        radarr_url=value("RADARR_URL", "http://demo-radarr.local:7878").rstrip("/"),
        radarr_api_key=value("RADARR_API_KEY", "demo-radarr-key"),
        seerr_kind=seerr_kind or "demo",
        seerr_url=value("SEERR_URL", "http://demo-seerr.local:5055").rstrip("/"),
        seerr_api_key=value("SEERR_API_KEY", "demo-seerr-key"),
        legacy_seerr_url=value("LEGACY_SEERR_URL", "").rstrip("/"),
        legacy_seerr_api_key=value("LEGACY_SEERR_API_KEY", ""),
        db_path=db_path,
        config_path=config_path,
        sync_interval_minutes=int(value("SYNC_INTERVAL_MINUTES", "60")),
    )
