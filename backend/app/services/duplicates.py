from __future__ import annotations

import sqlite3

from app import db
from app.clients.plex import PlexClient
from app.clients.radarr import RadarrClient
from app.clients.sonarr import SonarrClient
from app.core.config import Settings
from app.models import (
    DuplicateItem,
    DuplicatesPreviewItem,
    DuplicatesPreviewPlan,
    DuplicatesPreviewStep,
    DuplicatesExecuteItem,
    DuplicatesExecuteResponse,
)
from app.services.configuration import is_placeholder
from app.services.duplicate_analysis import parse_episode
from app.services.format import human_size


def _is_local_path(path: str, settings: Settings) -> bool:
    """A path is safe to delete only if it sits under a configured local prefix
    and under none of the protected prefixes. Defence-in-depth before any delete.
    """
    under_local = any(path.startswith(prefix) for prefix in settings.local_media_paths)
    under_protected = any(path.startswith(prefix) for prefix in settings.protected_media_paths)
    return bool(settings.local_media_paths) and under_local and not under_protected


async def build_duplicates_preview_plan(
    settings: Settings,
    items: list[DuplicateItem],
) -> DuplicatesPreviewPlan:
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

    plan_items: list[DuplicatesPreviewItem] = []
    for item in items:
        if item.media_type == "movie":
            plan_items.append(await _movie_plan(item, radarr))
        else:
            plan_items.append(await _show_plan(item, sonarr))

    total = sum(i.reclaimable_bytes for i in plan_items)
    return DuplicatesPreviewPlan(items=plan_items, total_reclaimable_bytes=total)


async def _show_plan(item: DuplicateItem, sonarr: SonarrClient | None) -> DuplicatesPreviewItem:
    steps: list[DuplicatesPreviewStep] = []
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
        steps.append(DuplicatesPreviewStep(
            service="Sonarr",
            action="delete_episode_file",
            detail=(
                f"{dv.identity}: would delete {file_label} "
                f"(local {dv.local_quality}, {human_size(dv.local_size_bytes)}) — "
                f"keeping NAS copy ({dv.nas_quality})."
            ),
        ))

    if unmonitor_episode_ids:
        steps.append(DuplicatesPreviewStep(
            service="Sonarr",
            action="unmonitor_episodes",
            detail=(
                f"Would unmonitor {len(set(unmonitor_episode_ids))} episode(s) so Sonarr "
                f"will not re-download the deleted files."
            ),
        ))

    return _finish_item(item, steps, warnings)


async def _movie_plan(item: DuplicateItem, radarr: RadarrClient | None) -> DuplicatesPreviewItem:
    steps: list[DuplicatesPreviewStep] = []
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
        steps.append(DuplicatesPreviewStep(
            service="Radarr",
            action="delete_movie_file",
            detail=(
                f"Would delete {file_label} "
                f"(local {dv.local_quality}, {human_size(dv.local_size_bytes)}) — "
                f"keeping NAS copy ({dv.nas_quality})."
            ),
        ))
    steps.append(DuplicatesPreviewStep(
        service="Radarr",
        action="unmonitor_movie",
        detail="Would unmonitor the movie so Radarr will not re-download the deleted file.",
    ))

    return _finish_item(item, steps, warnings)


def _finish_item(
    item: DuplicateItem,
    steps: list[DuplicatesPreviewStep],
    warnings: list[str],
) -> DuplicatesPreviewItem:
    if steps:  # only add follow-up steps when there is something to delete
        steps.append(DuplicatesPreviewStep(
            service="Plex",
            action="refresh_library",
            detail=f"Would refresh Plex library '{item.library}'. NAS copy remains available.",
        ))
        nas_sample = item.duplicate_versions[0].nas_path if item.duplicate_versions else ""
        steps.append(DuplicatesPreviewStep(
            service="Info",
            action="nas_copy_retained",
            detail=f"NAS copies are KEPT (protected path), e.g. {nas_sample}",
        ))

    return DuplicatesPreviewItem(
        media_item_id=item.id,
        title=item.title,
        library=item.library,
        manager_kind=item.manager_kind,
        episode_count=len(item.duplicate_versions),
        reclaimable_bytes=item.reclaimable_bytes if steps else 0,
        steps=steps,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Real execution: delete the local copies via Sonarr/Radarr, unmonitor so they
# are not re-downloaded, refresh Plex, and update the local cache. NAS copies
# (protected paths) are never touched.
# --------------------------------------------------------------------------- #


async def execute_duplicates_plan(
    settings: Settings,
    conn: sqlite3.Connection,
    items: list[DuplicateItem],
) -> DuplicatesExecuteResponse:
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
    plex_sections: dict[str, str] = {}
    if not is_placeholder(settings.plex_token):
        try:
            libraries = await PlexClient(settings.plex_url, settings.plex_token).list_libraries()
            plex_sections = {section.title: section.key for section in libraries}
        except Exception:
            pass

    result_items: list[DuplicatesExecuteItem] = []
    for item in items:
        if item.media_type == "movie":
            result_items.append(await _execute_movie(settings, conn, item, radarr, plex_sections))
        else:
            result_items.append(await _execute_show(settings, conn, item, sonarr, plex_sections))

    return DuplicatesExecuteResponse(
        items=result_items,
        deleted_file_count=sum(i.deleted_file_count for i in result_items),
        reclaimed_bytes=sum(i.reclaimed_bytes for i in result_items),
    )


async def _refresh_plex(settings: Settings, library: str, plex_sections: dict[str, str], steps: list[DuplicatesPreviewStep], warnings: list[str]) -> None:
    section_key = plex_sections.get(library)
    if not section_key:
        warnings.append(f"Plex library '{library}' not found; skipped refresh.")
        return
    try:
        await PlexClient(settings.plex_url, settings.plex_token).refresh_library_section(section_key)
        steps.append(DuplicatesPreviewStep(service="Plex", action="refresh_library", simulated=False,
                                          detail=f"Refreshed Plex library '{library}'. NAS copy remains available."))
    except Exception as exc:
        warnings.append(f"Plex refresh failed: {type(exc).__name__}: {exc}")


async def _execute_show(
    settings: Settings,
    conn: sqlite3.Connection,
    item: DuplicateItem,
    sonarr: SonarrClient | None,
    plex_sections: dict[str, str],
) -> DuplicatesExecuteItem:
    steps: list[DuplicatesPreviewStep] = []
    warnings: list[str] = []
    deleted_paths: list[str] = []
    reclaimed = 0

    if item.manager_kind != "sonarr" or item.manager_id is None or sonarr is None:
        warnings.append("Not managed by Sonarr — skipped (direct-file deletion requires a filesystem mount).")
        return _execute_result(item, steps, warnings, 0, 0)

    try:
        episodes = await sonarr.list_episodes(item.manager_id)
        files = await sonarr.list_episode_files(item.manager_id)
    except Exception as exc:
        warnings.append(f"Could not load Sonarr episode data: {type(exc).__name__}: {exc}")
        return _execute_result(item, steps, warnings, 0, 0)

    episode_by_number = {(e.get("seasonNumber"), e.get("episodeNumber")): e for e in episodes}
    path_by_file_id = {f.get("id"): f.get("path", "") for f in files}

    deleted_file_ids: set[int] = set()
    unmonitor_ids: set[int] = set()
    for dv in item.duplicate_versions:
        season, eps = parse_episode(dv.identity)
        file_id: int | None = None
        local_episode_ids: list[int] = []
        for ep in eps:
            episode = episode_by_number.get((season, ep))
            if not episode:
                continue
            if episode.get("id") is not None:
                local_episode_ids.append(int(episode["id"]))
            if episode.get("episodeFileId"):
                file_id = int(episode["episodeFileId"])

        if file_id is None:
            warnings.append(f"{dv.identity}: could not resolve Sonarr episode file; skipped.")
            continue
        if file_id in deleted_file_ids:
            continue

        # SAFETY: only delete if Sonarr's path for this file is under a local prefix.
        resolved_path = path_by_file_id.get(file_id, dv.local_path)
        if not _is_local_path(resolved_path, settings):
            warnings.append(f"{dv.identity}: resolved path is not under a local prefix; skipped for safety ({resolved_path}).")
            continue

        try:
            await sonarr.delete_episode_file(file_id, confirm=True)
        except Exception as exc:
            warnings.append(f"{dv.identity}: delete failed: {type(exc).__name__}: {exc}")
            continue

        deleted_file_ids.add(file_id)
        deleted_paths.append(resolved_path)
        reclaimed += dv.local_size_bytes
        unmonitor_ids.update(local_episode_ids)
        steps.append(DuplicatesPreviewStep(
            service="Sonarr", action="delete_episode_file", simulated=False,
            detail=f"{dv.identity}: deleted episodeFile {file_id} (local {dv.local_quality}, {human_size(dv.local_size_bytes)}).",
        ))

    if unmonitor_ids:
        try:
            await sonarr.set_episodes_monitored(sorted(unmonitor_ids), monitored=False)
            steps.append(DuplicatesPreviewStep(service="Sonarr", action="unmonitor_episodes", simulated=False,
                                              detail=f"Unmonitored {len(unmonitor_ids)} episode(s) so Sonarr will not re-download them."))
        except Exception as exc:
            warnings.append(f"Unmonitor failed: {type(exc).__name__}: {exc}")

    if deleted_paths:
        await _refresh_plex(settings, item.library, plex_sections, steps, warnings)
        db.remove_file_versions(conn, item.id, deleted_paths)

    return _execute_result(item, steps, warnings, len(deleted_file_ids), reclaimed)


async def _execute_movie(
    settings: Settings,
    conn: sqlite3.Connection,
    item: DuplicateItem,
    radarr: RadarrClient | None,
    plex_sections: dict[str, str],
) -> DuplicatesExecuteItem:
    steps: list[DuplicatesPreviewStep] = []
    warnings: list[str] = []

    if item.manager_kind != "radarr" or item.manager_id is None or radarr is None:
        warnings.append("Not managed by Radarr — skipped (direct-file deletion requires a filesystem mount).")
        return _execute_result(item, steps, warnings, 0, 0)

    try:
        files = await radarr.list_movie_files(item.manager_id)
    except Exception as exc:
        warnings.append(f"Could not load Radarr movie files: {type(exc).__name__}: {exc}")
        return _execute_result(item, steps, warnings, 0, 0)

    local_paths = {dv.local_path for dv in item.duplicate_versions}
    deleted_paths: list[str] = []
    reclaimed = 0
    for f in files:
        path = f.get("path", "")
        if path not in local_paths:
            continue
        if not _is_local_path(path, settings):
            warnings.append(f"Resolved path is not under a local prefix; skipped for safety ({path}).")
            continue
        try:
            await radarr.delete_movie_file(int(f["id"]), confirm=True)
        except Exception as exc:
            warnings.append(f"Delete failed for {path}: {type(exc).__name__}: {exc}")
            continue
        deleted_paths.append(path)
        dv = next((d for d in item.duplicate_versions if d.local_path == path), None)
        reclaimed += dv.local_size_bytes if dv else 0
        steps.append(DuplicatesPreviewStep(service="Radarr", action="delete_movie_file", simulated=False,
                                          detail=f"Deleted movieFile {f['id']} (local {dv.local_quality if dv else '?'}, {human_size(dv.local_size_bytes if dv else 0)})."))

    if deleted_paths:
        try:
            await radarr.set_movies_monitored([item.manager_id], monitored=False)
            steps.append(DuplicatesPreviewStep(service="Radarr", action="unmonitor_movie", simulated=False,
                                              detail="Unmonitored the movie so Radarr will not re-download it."))
        except Exception as exc:
            warnings.append(f"Unmonitor failed: {type(exc).__name__}: {exc}")
        await _refresh_plex(settings, item.library, plex_sections, steps, warnings)
        db.remove_file_versions(conn, item.id, deleted_paths)

    return _execute_result(item, steps, warnings, len(deleted_paths), reclaimed)


def _execute_result(item: DuplicateItem, steps, warnings, deleted_count, reclaimed) -> DuplicatesExecuteItem:
    return DuplicatesExecuteItem(
        media_item_id=item.id,
        title=item.title,
        library=item.library,
        manager_kind=item.manager_kind,
        deleted_file_count=deleted_count,
        reclaimed_bytes=reclaimed,
        steps=steps,
        warnings=warnings,
    )
