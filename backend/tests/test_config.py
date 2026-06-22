from __future__ import annotations

import pytest

from app.core.config import ConfigurationError, load_settings


def test_missing_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "PLEX_MANAGER_DEMO_MODE",
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
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ConfigurationError):
        load_settings()


def test_demo_mode_allows_missing_external_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    settings = load_settings()
    assert settings.demo_mode is True
    assert settings.plex_library_names == ("Movies", "TV Shows")

