from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "false")
    monkeypatch.setenv("PLEX_URL", "http://plex.local:32400")
    monkeypatch.setenv("PLEX_TOKEN", "replace-me")
    monkeypatch.setenv("PLEX_LIBRARY_NAMES", "Movies,TV Shows")
    monkeypatch.setenv("TAUTULLI_URL", "http://tautulli.local:8181")
    monkeypatch.setenv("TAUTULLI_API_KEY", "replace-me")
    monkeypatch.setenv("SONARR_URL", "http://sonarr.local:8989")
    monkeypatch.setenv("SONARR_API_KEY", "replace-me")
    monkeypatch.setenv("RADARR_URL", "http://radarr.local:7878")
    monkeypatch.setenv("RADARR_API_KEY", "replace-me")
    monkeypatch.setenv("SEERR_KIND", "overseerr")
    monkeypatch.setenv("SEERR_URL", "http://seerr.local:5055")
    monkeypatch.setenv("SEERR_API_KEY", "replace-me")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "plex-manager.db"))
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "config.json"))

    from app.main import create_app

    return TestClient(create_app())


def test_config_route_never_returns_secret_values(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert "plex_token" not in payload
    assert payload["plex_token_set"] is True
    assert payload["plex_token_placeholder"] is True


def test_update_config_writes_overlay_and_refreshes_settings(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.put(
        "/api/config",
        json={
            "plex_url": "http://plex.example:32400",
            "plex_token": "plex-token",
            "plex_library_names": ["Movies", "TV Shows"],
            "tautulli_url": "http://tautulli.example:8181",
            "tautulli_api_key": "tautulli-key",
            "sonarr_url": "http://sonarr.example:8989",
            "sonarr_api_key": "sonarr-key",
            "radarr_url": "http://radarr.example:7878",
            "radarr_api_key": "radarr-key",
            "seerr_kind": "jellyseerr",
            "seerr_url": "http://seerr.example:5055",
            "seerr_api_key": "seerr-key",
            "sync_interval_minutes": 30,
        },
    )

    assert response.status_code == 200
    assert response.json()["plex_token_placeholder"] is False

    payload = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert payload["PLEX_URL"] == "http://plex.example:32400"
    assert payload["PLEX_TOKEN"] == "plex-token"
    assert payload["SEERR_KIND"] == "jellyseerr"


def test_validation_reports_placeholder_credentials_without_network(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/config/validate")

    assert response.status_code == 200
    states = {item["name"]: item["state"] for item in response.json()["integrations"]}
    assert states == {
        "Plex": "missing",
        "Tautulli": "missing",
        "Sonarr": "missing",
        "Radarr": "missing",
        "Seerr": "missing",
    }

