from __future__ import annotations

from app.clients.radarr import RadarrClient
from app.clients.sonarr import SonarrClient
from app.core.config import Settings
from app.models import (
    DuplicateItem,
    DuplicatesDryRunItem,
    DuplicatesDryRunPlan,
    DuplicatesDryRunStep,
)
from app.services.configuration import is_placeholder
from app.services.duplicate_analysis import parse_episode
from app.services.format import human_size


async def build_duplicates_dry_run_plan(
    settings: Settings,
    items: list[DuplicateItem],
) -> DuplicatesDryRunPlan:
    """Build a precise, non-mutating plan for removing local duplicate files.

    Deletion is per-file via the Sonarr/Radarr APIs, plus an unmonitor step so
    the managers will not re-download. NAS copies are never touched.
    """
    sonarr = (
        SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        if not is_placeholder(settings.sonarr_api_key)
        else None
    )
    radarr = (
        RadarrClient(settings.radarr_url, settings.radarr_api_key)
        if not is_placeholder(settings.radarr_api_key)
        else None
    )

    plan_items: list[DuplicatesDryRunItem] = []
    for item in items:
        if item.media_type == "movie":
            plan_items.append(await _movie_plan(item, radarr))
        else:
            plan_items.append(await _show_plan(item, sonarr))

    total = sum(i.reclaimable_bytes for i in plan_items)
    return DuplicatesDryRunPlan(items=plan_items, total_reclaimable_bytes=total)


async def _show_plan(item: DuplicateItem, sonarr: SonarrClient | None) -> DuplicatesDryRunItem:
    steps: list[DuplicatesDryRunStep] = []
    warnings: list[str] = []

    if item.manager_kind != "sonarr" or item.manager_id is None:
        warnings.append(
            "Not managed by Sonarr — direct-file deletion (filesystem mount) is required; skipped for now."
        )
        return _finish_item(item, steps, warnings)

    episode_by_number: dict[tuple[int, int], dict] = {}
    if sonarr is not None:
        try:
            episodes = await sonarr.list_episodes(item.manager_id)
            episode_by_number = {
                (e.get("seasonNumber"), e.get("episodeNumber")): e for e in episodes
            }
        except Exception:
            warnings.append("Could not reach Sonarr to resolve episode file IDs; IDs shown as unknown.")

    unmonitor_episode_ids: list[int] = []
    file_ids_seen: set[int] = set()
    for dv in item.duplicate_versions:
        season, eps = parse_episode(dv.identity)
        file_id: int | None = None
        for ep in eps:
            episode = episode_by_number.get((season, ep))
            if episode:
                if episode.get("id") is not None:
                    unmonitor_episode_ids.append(int(episode["id"]))
                if episode.get("episodeFileId"):
                    file_id = int(episode["episodeFileId"])
        file_label = f"episodeFile {file_id}" if file_id else "episodeFile (unresolved)"
        if file_id is not None and file_id in file_ids_seen:
            continue
        if file_id is not None:
            file_ids_seen.add(file_id)
        steps.append(DuplicatesDryRunStep(
            service="Sonarr",
            action="delete_episode_file",
            detail=(
                f"{dv.identity}: would delete {file_label} "
                f"(local {dv.local_quality}, {human_size(dv.local_size_bytes)}) — "
                f"keeping NAS copy ({dv.nas_quality})."
            ),
        ))

    if unmonitor_episode_ids:
        steps.append(DuplicatesDryRunStep(
            service="Sonarr",
            action="unmonitor_episodes",
            detail=(
                f"Would unmonitor {len(set(unmonitor_episode_ids))} episode(s) so Sonarr "
                f"will not re-download the deleted files."
            ),
        ))

    return _finish_item(item, steps, warnings)


async def _movie_plan(item: DuplicateItem, radarr: RadarrClient | None) -> DuplicatesDryRunItem:
    steps: list[DuplicatesDryRunStep] = []
    warnings: list[str] = []

    if item.manager_kind != "radarr" or item.manager_id is None:
        warnings.append(
            "Not managed by Radarr — direct-file deletion (filesystem mount) is required; skipped for now."
        )
        return _finish_item(item, steps, warnings)

    movie_file_id: int | None = None
    if radarr is not None:
        try:
            files = await radarr.list_movie_files(item.manager_id)
            local_paths = {dv.local_path for dv in item.duplicate_versions}
            match = next((f for f in files if f.get("path") in local_paths), files[0] if files else None)
            if match and match.get("id") is not None:
                movie_file_id = int(match["id"])
        except Exception:
            warnings.append("Could not reach Radarr to resolve the movie file ID; ID shown as unknown.")

    for dv in item.duplicate_versions:
        file_label = f"movieFile {movie_file_id}" if movie_file_id else "movieFile (unresolved)"
        steps.append(DuplicatesDryRunStep(
            service="Radarr",
            action="delete_movie_file",
            detail=(
                f"Would delete {file_label} "
                f"(local {dv.local_quality}, {human_size(dv.local_size_bytes)}) — "
                f"keeping NAS copy ({dv.nas_quality})."
            ),
        ))
    steps.append(DuplicatesDryRunStep(
        service="Radarr",
        action="unmonitor_movie",
        detail="Would unmonitor the movie so Radarr will not re-download the deleted file.",
    ))

    return _finish_item(item, steps, warnings)


def _finish_item(
    item: DuplicateItem,
    steps: list[DuplicatesDryRunStep],
    warnings: list[str],
) -> DuplicatesDryRunItem:
    if steps:  # only add follow-up steps when there is something to delete
        steps.append(DuplicatesDryRunStep(
            service="Plex",
            action="refresh_library",
            detail=f"Would refresh Plex library '{item.library}'. NAS copy remains available.",
        ))
        nas_sample = item.duplicate_versions[0].nas_path if item.duplicate_versions else ""
        steps.append(DuplicatesDryRunStep(
            service="Info",
            action="nas_copy_retained",
            detail=f"NAS copies are KEPT (protected path), e.g. {nas_sample}",
        ))

    return DuplicatesDryRunItem(
        media_item_id=item.id,
        title=item.title,
        library=item.library,
        manager_kind=item.manager_kind,
        episode_count=len(item.duplicate_versions),
        reclaimable_bytes=item.reclaimable_bytes if steps else 0,
        steps=steps,
        warnings=warnings,
    )
