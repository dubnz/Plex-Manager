from __future__ import annotations

import sqlite3

from app import db
from app.clients.plex import PlexClient
from app.clients.radarr import RadarrClient
from app.clients.seerr import SeerrClient
from app.clients.sonarr import SonarrClient
from app.core.config import Settings
from app.models import DeletePreviewItem, DeletePreviewPlan, DeletePreviewStep, DeleteExecuteResponse, MediaItem
from app.services.configuration import is_placeholder


def build_delete_preview_plan(items: list[MediaItem], *, delete_files: bool) -> DeletePreviewPlan:
    plan_items: list[DeletePreviewItem] = []
    for item in items:
        steps: list[DeletePreviewStep] = []
        warnings: list[str] = []

        if item.manager_kind == "sonarr":
            steps.append(
                DeletePreviewStep(
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
                DeletePreviewStep(
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
                DeletePreviewStep(
                    service="Seerr",
                    action="mark_unavailable",
                    detail="Would mark associated request/media unavailable after manager delete succeeds.",
                ),
                DeletePreviewStep(
                    service="Plex",
                    action="refresh_library",
                    detail="Would refresh the exact selected Plex library section after external deletion.",
                ),
                DeletePreviewStep(
                    service="Local DB",
                    action="update_cache",
                    detail="Would mark the cached item removed or unavailable after verification.",
                ),
            ]
        )

        plan_items.append(
            DeletePreviewItem(
                media_item_id=item.id,
                title=item.title,
                library=item.library,
                manager_kind=item.manager_kind,
                file_size_bytes=item.file_size_bytes,
                steps=steps,
                warnings=warnings,
            )
        )

    return DeletePreviewPlan(
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

    plan_items: list[DeletePreviewItem] = []
    deleted_ids: list[int] = []
    global_warnings: list[str] = []
    plex_sections: dict[str, str] = {}

    seerr_media_by_rating_key: dict[str, int] = {}
    seerr_enabled = not settings.demo_mode and not is_placeholder(settings.seerr_api_key)
    if settings.demo_mode:
        global_warnings.append("Demo mode: no external Radarr, Sonarr, Seerr, or Plex mutation was made.")
    else:
        try:
            plex_sections = {section.title: section.key for section in await PlexClient(settings.plex_url, settings.plex_token).list_libraries()}
        except Exception as exc:
            global_warnings.append(f"Plex library refresh was skipped: {type(exc).__name__}: {exc}")
        if seerr_enabled:
            try:
                seerr_client = SeerrClient(settings.seerr_url, settings.seerr_api_key, settings.seerr_kind)
                seerr_media_by_rating_key = await seerr_client.media_id_by_rating_key()
            except Exception as exc:
                global_warnings.append(f"Seerr media lookup skipped: {type(exc).__name__}: {exc}")

    for item in items:
        steps: list[DeletePreviewStep] = []
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
                DeletePreviewStep(
                    service="Sonarr",
                    action="delete_series",
                    simulated=False,
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
                DeletePreviewStep(
                    service="Radarr",
                    action="delete_movie",
                    simulated=False,
                    detail=f"Deleted Radarr movie id {item.manager_id}; delete files: {'yes' if delete_files else 'no'}.",
                )
            )
        else:
            warnings.append("Skipped: no Sonarr/Radarr manager id is linked for this item.")

        if manager_deleted:
            seerr_media_id = seerr_media_by_rating_key.get(str(item.plex_rating_key))
            if settings.demo_mode:
                steps.append(DeletePreviewStep(
                    service="Seerr", action="mark_unavailable",
                    detail="Demo mode: would mark unavailable in Seerr.",
                ))
            elif not seerr_enabled:
                steps.append(DeletePreviewStep(
                    service="Seerr", action="mark_unavailable",
                    detail="Skipped: Seerr is not configured.",
                ))
            elif seerr_media_id is None:
                steps.append(DeletePreviewStep(
                    service="Seerr", action="mark_unavailable",
                    detail="Skipped: title is not tracked in Seerr.",
                ))
            else:
                try:
                    await SeerrClient(settings.seerr_url, settings.seerr_api_key, settings.seerr_kind).mark_unavailable(
                        seerr_media_id, confirm=True
                    )
                    steps.append(DeletePreviewStep(
                        service="Seerr", action="mark_unavailable", simulated=False,
                        detail=f"Marked unavailable in Seerr (media id {seerr_media_id}); title can be re-requested.",
                    ))
                except Exception as exc:
                    warnings.append(f"Seerr mark-unavailable failed: {type(exc).__name__}: {exc}")

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
                DeletePreviewStep(
                    service="Plex",
                    action="refresh_library",
                    simulated=settings.demo_mode or not section_key,
                    detail=plex_detail,
                )
            )
            deleted_ids.append(item.id)
            steps.append(
                DeletePreviewStep(
                    service="Local DB",
                    action="update_cache",
                    simulated=False,
                    detail="Marked the cached item unavailable after manager deletion.",
                )
            )

        plan_items.append(
            DeletePreviewItem(
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
