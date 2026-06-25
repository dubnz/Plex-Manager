from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from app.db import connect, init_database, list_duplicates, upsert_media_items
from app.services import duplicates as dup_service


def _new_conn():
    db_path = Path(tempfile.mkdtemp()) / "test.db"
    conn = connect(db_path)
    init_database(conn)
    return conn


# Neutral example prefixes — the logic is prefix-agnostic and these stand in for
# any local/protected layout without encoding a real deployment.
LOCAL = ("/mnt/local/movies", "/mnt/local/tv")
PROTECTED = ("/mnt/remote-movies", "/mnt/remote-tv")


class FakeSonarr:
    def __init__(self):
        self.deleted: list[int] = []
        self.unmonitored: list[int] = []

    async def list_episodes(self, series_id):
        return [
            {"seasonNumber": 1, "episodeNumber": 1, "id": 101, "episodeFileId": 5001, "monitored": True},
            {"seasonNumber": 1, "episodeNumber": 2, "id": 102, "episodeFileId": 5002, "monitored": True},
        ]

    async def list_episode_files(self, series_id):
        return [
            {"id": 5001, "path": "/mnt/local/tv/Show/Season 01/Show - S01E01 [WEBDL-2160p].mkv"},
            {"id": 5002, "path": "/mnt/local/tv/Show/Season 01/Show - S01E02 [WEBDL-2160p].mkv"},
        ]

    async def delete_episode_file(self, file_id, *, confirm=False):
        assert confirm is True
        self.deleted.append(file_id)

    async def set_episodes_monitored(self, episode_ids, monitored):
        assert monitored is False
        self.unmonitored.extend(episode_ids)


def _conn_with_show():
    conn = _new_conn()

    def lp(ep): return f"/mnt/local/tv/Show/Season 01/Show - S01E{ep:02d} [WEBDL-2160p].mkv"
    def np(ep): return f"/mnt/remote-tv/Show/Season 01/Show - S01E{ep:02d} HDTV-720p.mkv"

    upsert_media_items(conn, [{
        "plex_rating_key": "k1", "library": "TV", "media_type": "show", "title": "Show",
        "added_at": "2024-01-01T00:00:00+00:00", "manager_kind": "sonarr", "manager_id": 7,
        "file_versions": [
            {"path": lp(1), "size": 1000}, {"path": lp(2), "size": 2000},
            {"path": np(1), "size": 500}, {"path": np(2), "size": 600},
        ],
    }])
    return conn


def _settings(monkeypatch):
    # Plex token left as a placeholder so execute skips the live Plex section
    # lookup (these tests stub Sonarr/Radarr and _refresh_plex directly).
    monkeypatch.setenv("PLEX_TOKEN", "demo-token")
    monkeypatch.setenv("SONARR_API_KEY", "real-sonarr")
    monkeypatch.setenv("RADARR_API_KEY", "real-radarr")
    monkeypatch.setenv("LOCAL_MEDIA_PATHS", ",".join(LOCAL))
    monkeypatch.setenv("PROTECTED_MEDIA_PATHS", ",".join(PROTECTED))
    from app.core.config import load_settings
    return load_settings()


def test_execute_deletes_only_local_files_and_unmonitors(monkeypatch):
    conn = _conn_with_show()
    settings = _settings(monkeypatch)
    fake = FakeSonarr()

    # Avoid real network: stub client constructors + Plex refresh.
    monkeypatch.setattr(dup_service, "SonarrClient", lambda *a, **k: fake)
    async def no_plex(*a, **k):
        return None
    monkeypatch.setattr(dup_service, "_refresh_plex", no_plex)

    items = list_duplicates(conn, LOCAL, PROTECTED)
    assert len(items) == 1

    result = asyncio.run(dup_service.execute_duplicates_plan(settings, conn, items))

    # Both local episode files deleted (5001, 5002); nothing from NAS.
    assert sorted(fake.deleted) == [5001, 5002]
    assert sorted(fake.unmonitored) == [101, 102]
    assert result.deleted_file_count == 2
    assert result.reclaimed_bytes == 3000  # 1000 + 2000 local sizes only

    # Local paths dropped from cache; NAS paths retained.
    row = conn.execute("SELECT file_versions_json FROM media_item WHERE id = ?", (items[0].id,)).fetchone()
    paths = [v["path"] for v in json.loads(row["file_versions_json"])]
    assert all(p.startswith("/mnt/remote-tv") for p in paths)
    assert len(paths) == 2


def test_execute_safety_skips_non_local_resolved_path(monkeypatch):
    conn = _conn_with_show()
    settings = _settings(monkeypatch)

    class EvilSonarr(FakeSonarr):
        async def list_episode_files(self, series_id):
            # Sonarr reports a PROTECTED path for the file — must be refused.
            return [
                {"id": 5001, "path": "/mnt/remote-tv/Show/Season 01/Show - S01E01.mkv"},
                {"id": 5002, "path": "/mnt/remote-tv/Show/Season 01/Show - S01E02.mkv"},
            ]

    fake = EvilSonarr()
    monkeypatch.setattr(dup_service, "SonarrClient", lambda *a, **k: fake)
    async def no_plex(*a, **k):
        return None
    monkeypatch.setattr(dup_service, "_refresh_plex", no_plex)

    items = list_duplicates(conn, LOCAL, PROTECTED)
    result = asyncio.run(dup_service.execute_duplicates_plan(settings, conn, items))

    assert fake.deleted == []  # nothing deleted
    assert result.deleted_file_count == 0
    assert any("not under a local prefix" in w for w in result.items[0].warnings)


def test_execute_unmanaged_item_skipped(monkeypatch):
    conn = _new_conn()
    upsert_media_items(conn, [{
        "plex_rating_key": "k2", "library": "TV", "media_type": "show", "title": "Manual Show",
        "added_at": "2024-01-01T00:00:00+00:00", "manager_kind": "none", "manager_id": None,
        "file_versions": [
            {"path": "/mnt/local/tv/Manual/Season 01/Manual - S01E01.mkv", "size": 1000},
            {"path": "/mnt/remote-tv/Manual/Season 01/Manual - S01E01.mkv", "size": 500},
        ],
    }])
    settings = _settings(monkeypatch)
    items = list_duplicates(conn, LOCAL, PROTECTED)
    result = asyncio.run(dup_service.execute_duplicates_plan(settings, conn, items))
    assert result.deleted_file_count == 0
    assert any("Not managed by Sonarr" in w for w in result.items[0].warnings)
