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


def test_delete_dry_run_route_uses_cached_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "demo.db"))

    from app.main import create_app

    client = TestClient(create_app())
    response = client.post("/api/actions/delete/dry-run", json={"media_item_ids": [1], "delete_files": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_confirmation"] is True
    assert payload["items"][0]["steps"][0]["dry_run"] is True
