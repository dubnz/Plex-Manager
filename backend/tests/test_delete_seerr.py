from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.db import connect, init_database
from app.models import MediaItem
from app.services import cleanup


def _conn():
    conn = connect(Path(tempfile.mkdtemp()) / "test.db")
    init_database(conn)
    return conn


class FakeSeerr:
    instances: list["FakeSeerr"] = []

    def __init__(self, *a, **k):
        self.unavailable: list[int] = []
        FakeSeerr.instances.append(self)

    async def media_id_by_rating_key(self, **kwargs):
        return {"14085": 555}  # ratingKey -> Seerr media id

    async def mark_unavailable(self, media_id, *, confirm=False):
        assert confirm is True
        self.unavailable.append(media_id)


class FakeRadarr:
    def __init__(self, *a, **k):
        self.deleted: list[int] = []

    async def delete_movie(self, movie_id, *, delete_files, confirm=False):
        assert confirm is True
        self.deleted.append(movie_id)


class FakePlex:
    def __init__(self, *a, **k):
        pass

    async def list_libraries(self):
        class S:  # minimal section
            title = "Movies"
            key = "1"
        return [S()]

    async def refresh_library_section(self, key):
        return None


def _settings(monkeypatch):
    monkeypatch.setenv("PLEX_MANAGER_DEMO_MODE", "false")
    monkeypatch.setenv("PLEX_URL", "http://plex.local:32400")
    monkeypatch.setenv("PLEX_TOKEN", "real-token")
    monkeypatch.setenv("TAUTULLI_URL", "http://tautulli.local:8181")
    monkeypatch.setenv("TAUTULLI_API_KEY", "real-tautulli")
    monkeypatch.setenv("SONARR_URL", "http://sonarr.local:8989")
    monkeypatch.setenv("SONARR_API_KEY", "real-sonarr")
    monkeypatch.setenv("RADARR_URL", "http://radarr.local:7878")
    monkeypatch.setenv("RADARR_API_KEY", "real-radarr")
    monkeypatch.setenv("SEERR_KIND", "jellyseerr")
    monkeypatch.setenv("SEERR_URL", "http://seerr.local:5055")
    monkeypatch.setenv("SEERR_API_KEY", "real-seerr")
    from app.core.config import load_settings
    return load_settings()


def _item():
    return MediaItem(
        id=1, plex_rating_key="14085", library="Movies", media_type="movie",
        title="Some Movie", year=2020, added_at=datetime.now(UTC),
        manager_kind="radarr", manager_id=42, file_size_bytes=1000,
    )


def test_delete_marks_matched_item_unavailable_in_seerr(monkeypatch):
    FakeSeerr.instances = []
    monkeypatch.setattr(cleanup, "SeerrClient", FakeSeerr)
    monkeypatch.setattr(cleanup, "RadarrClient", FakeRadarr)
    monkeypatch.setattr(cleanup, "PlexClient", FakePlex)
    settings = _settings(monkeypatch)
    conn = _conn()

    result = asyncio.run(cleanup.execute_delete_plan(
        settings, conn, [_item()], delete_files=True, confirmation="DELETE",
    ))

    # The matched rating key (14085 -> media id 555) was marked unavailable.
    marked = [mid for inst in FakeSeerr.instances for mid in inst.unavailable]
    assert 555 in marked
    assert result.deleted_count == 1
    seerr_steps = [s for i in result.items for s in i.steps if s.service == "Seerr"]
    assert any("Marked unavailable" in s.detail and s.simulated is False for s in seerr_steps)


def test_delete_skips_seerr_when_rating_key_not_tracked(monkeypatch):
    FakeSeerr.instances = []
    monkeypatch.setattr(cleanup, "SeerrClient", FakeSeerr)
    monkeypatch.setattr(cleanup, "RadarrClient", FakeRadarr)
    monkeypatch.setattr(cleanup, "PlexClient", FakePlex)
    settings = _settings(monkeypatch)
    conn = _conn()

    item = _item()
    item.plex_rating_key = "99999"  # not in the Seerr map
    result = asyncio.run(cleanup.execute_delete_plan(
        settings, conn, [item], delete_files=True, confirmation="DELETE",
    ))

    marked = [mid for inst in FakeSeerr.instances for mid in inst.unavailable]
    assert marked == []  # nothing marked
    seerr_steps = [s for i in result.items for s in i.steps if s.service == "Seerr"]
    assert any("not tracked in Seerr" in s.detail for s in seerr_steps)
