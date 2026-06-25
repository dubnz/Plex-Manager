from __future__ import annotations

import sqlite3

from app import db
from app.clients.plex import PlexClient
from app.clients.radarr import RadarrClient
from app.clients.sonarr import SonarrClient
from app.core.config import Settings
from app.models import DeleteDryRunItem, DeleteDryRunPlan, DeleteDryRunStep, DeleteExecuteResponse, MediaItem


def build_delete_dry_run_plan(items: list[MediaItem], *, delete_files: bool) -> DeleteDryRunPlan:
    plan_items: list[DeleteDryRunItem] = []
    for item in items:
        steps: list[DeleteDryRunStep] = []
        warnings: list[str] = []

        if item.manager_kind == "sonarr":
            steps.append(
                DeleteDryRunStep(
                    service="Sonarr",
                    action="delete_series",
                    detail=(
                        f"Would delete Sonarr series id {item.manager_id}; "
                        f"delete files: {'yes' if delete_files else 'no'}."
                    ),
                )
            )
        elif item.manager_kind == "radarr":
            steps.append(
                DeleteDryRunStep(
                    service="Radarr",
                    action="delete_movie",
                    detail=(
                        f"Would delete Radarr movie id {item.manager_id}; "
                        f"delete files: {'yes' if delete_files else 'no'}."
                    ),
                )
            )
        else:
            warnings.append("No Sonarr/Radarr manager id is linked; Plex direct delete would need separate confirmation.")

        steps.extend(
            [
                DeleteDryRunStep(
                    service="Seerr",
                    action="mark_unavailable",
                    detail="Would mark associated request/media unavailable after manager delete succeeds.",
                ),
                DeleteDryRunStep(
                    service="Plex",
                    action="refresh_library",
                    detail="Would refresh the exact selected Plex library section after external deletion.",
                ),
                DeleteDryRunStep(
                    service="Local DB",
                    action="update_cache",
                    detail="Would mark the cached item removed or unavailable after verification.",
                ),
            ]
        )

        plan_items.append(
            DeleteDryRunItem(
                media_item_id=item.id,
                title=item.title,
                library=item.library,
                manager_kind=item.manager_kind,
                file_size_bytes=item.file_size_bytes,
                steps=steps,
                warnings=warnings,
            )
        )

    return DeleteDryRunPlan(
        items=plan_items,
        storage_reclaim_estimate_bytes=sum(item.file_size_bytes for item in items if delete_files),
        global_warnings=[
            "Preview only: confirm to permanently delete the entire item from Sonarr/Radarr and disk.",
        ],
    )


async def execute_delete_plan(
    settings: Settings,
    conn: sqlite3.Connection,
    items: list[MediaItem],
    *,
    delete_files: bool,
    confirmation: str,
) -> DeleteExecuteResponse:
    if confirmation != "DELETE":
        raise ValueError("Type DELETE to confirm real deletion.")

    plan_items: list[DeleteDryRunItem] = []
    deleted_ids: list[int] = []
    global_warnings: list[str] = []
    plex_sections: dict[str, str] = {}

    if settings.demo_mode:
        global_warnings.append("Demo mode: no external Radarr, Sonarr, Seerr, or Plex mutation was made.")
    else:
        try:
            plex_sections = {section.title: section.key for section in await PlexClient(settings.plex_url, settings.plex_token).list_libraries()}
        except Exception as exc:
            global_warnings.append(f"Plex library refresh was skipped: {type(exc).__name__}: {exc}")

    for item in items:
        steps: list[DeleteDryRunStep] = []
        warnings: list[str] = []
        manager_deleted = False

        if item.manager_kind == "sonarr" and item.manager_id is not None:
            if settings.demo_mode:
                manager_deleted = True
            else:
                await SonarrClient(settings.sonarr_url, settings.sonarr_api_key).delete_series(
                    item.manager_id,
                    delete_files=delete_files,
                    confirm=True,
                )
                manager_deleted = True
            steps.append(
                DeleteDryRunStep(
                    service="Sonarr",
                    action="delete_series",
                    dry_run=False,
                    detail=f"Deleted Sonarr series id {item.manager_id}; delete files: {'yes' if delete_files else 'no'}.",
                )
            )
        elif item.manager_kind == "radarr" and item.manager_id is not None:
            if settings.demo_mode:
                manager_deleted = True
            else:
                await RadarrClient(settings.radarr_url, settings.radarr_api_key).delete_movie(
                    item.manager_id,
                    delete_files=delete_files,
                    confirm=True,
                )
                manager_deleted = True
            steps.append(
                DeleteDryRunStep(
                    service="Radarr",
                    action="delete_movie",
                    dry_run=False,
                    detail=f"Deleted Radarr movie id {item.manager_id}; delete files: {'yes' if delete_files else 'no'}.",
                )
            )
        else:
            warnings.append("Skipped: no Sonarr/Radarr manager id is linked for this item.")

        steps.append(
            DeleteDryRunStep(
                service="Seerr",
                action="mark_unavailable",
                detail="Skipped: Seerr unavailable mutation is not enabled until the exact endpoint is verified.",
            )
        )

        if manager_deleted:
            section_key = plex_sections.get(item.library)
            if section_key and not settings.demo_mode:
                await PlexClient(settings.plex_url, settings.plex_token).refresh_library_section(section_key)
                plex_detail = f"Refreshed Plex library section '{item.library}'."
            elif settings.demo_mode:
                plex_detail = f"Demo mode: would refresh Plex library section '{item.library}'."
            else:
                plex_detail = f"Skipped: Plex library section '{item.library}' was not found."
                warnings.append(plex_detail)
            steps.append(
                DeleteDryRunStep(
                    service="Plex",
                    action="refresh_library",
                    dry_run=settings.demo_mode or not section_key,
                    detail=plex_detail,
                )
            )
            deleted_ids.append(item.id)
            steps.append(
                DeleteDryRunStep(
                    service="Local DB",
                    action="update_cache",
                    dry_run=False,
                    detail="Marked the cached item unavailable after manager deletion.",
                )
            )

        plan_items.append(
            DeleteDryRunItem(
                media_item_id=item.id,
                title=item.title,
                library=item.library,
                manager_kind=item.manager_kind,
                file_size_bytes=item.file_size_bytes,
                steps=steps,
                warnings=warnings,
            )
        )

    db.mark_media_unavailable(conn, deleted_ids)
    return DeleteExecuteResponse(
        items=plan_items,
        deleted_count=len(deleted_ids),
        storage_reclaim_estimate_bytes=sum(item.file_size_bytes for item in items if item.id in set(deleted_ids) and delete_files),
        global_warnings=global_warnings,
    )
