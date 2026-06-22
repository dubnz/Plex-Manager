from __future__ import annotations

from datetime import UTC, datetime

from app.models import MediaItem
from app.services.cleanup import build_delete_dry_run_plan


def test_delete_dry_run_never_mutates_and_estimates_storage() -> None:
    item = MediaItem(
        id=1,
        plex_rating_key="abc",
        library="Movies",
        media_type="movie",
        title="Test Movie",
        year=2020,
        added_at=datetime.now(UTC),
        manager_kind="radarr",
        manager_id=9,
        file_size_bytes=2048,
    )

    plan = build_delete_dry_run_plan([item], delete_files=True)

    assert plan.requires_confirmation is True
    assert plan.storage_reclaim_estimate_bytes == 2048
    assert plan.items[0].steps[0].service == "Radarr"
    assert all(step.dry_run for step in plan.items[0].steps)
    assert "Dry-run only" in plan.global_warnings[0]

