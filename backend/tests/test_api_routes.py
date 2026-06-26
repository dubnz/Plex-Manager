from __future__ import annotations

from fastapi.testclient import TestClient


def test_media_route_returns_seeded_demo_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.get("/api/media", params={"library": "Movies"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["items"][0]["library"] == "Movies"


def test_delete_preview_route_uses_cached_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.post("/api/actions/delete/preview", json={"media_item_ids": [1], "delete_files": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_confirmation"] is True
    assert payload["items"][0]["steps"][0]["simulated"] is True


def test_sync_route_blocks_placeholder_plex_token(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "config.json"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.post("/api/sync/run")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert "Plex token" in response.json()["detail"]


def test_delete_execute_requires_confirmation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/actions/delete/execute",
        json={"media_item_ids": [1], "delete_files": True, "confirmation": "delete"},
    )

    assert response.status_code == 400
    assert "DELETE" in response.json()["detail"]


def test_delete_execute_demo_marks_cache_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/actions/delete/execute",
        json={"media_item_ids": [1], "delete_files": True, "confirmation": "DELETE"},
    )

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1

    media = client.get("/api/media", params={"library": "Movies"}).json()["items"]
    deleted = next(item for item in media if item["id"] == 1)
    assert deleted["available"] is False
