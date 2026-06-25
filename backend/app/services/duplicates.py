from __future__ import annotations

from app.models import (
    DuplicateItem,
    DuplicatesDryRunItem,
    DuplicatesDryRunPlan,
    DuplicatesDryRunStep,
)


def build_duplicates_dry_run_plan(items: list[DuplicateItem]) -> DuplicatesDryRunPlan:
    """Build a dry-run plan for removing local copies of duplicated media.

    Only the local_paths are targeted for removal. nas_paths are never touched.
    """
    plan_items: list[DuplicatesDryRunItem] = []
    global_warnings: list[str] = []

    for item in items:
        steps: list[DuplicatesDryRunStep] = []
        warnings: list[str] = []

        local_paths_display = "\n  ".join(item.local_paths)

        if item.manager_kind == "radarr":
            steps.append(DuplicatesDryRunStep(
                service="Radarr",
                action="remove_movie",
                dry_run=True,
                detail=f"Would delete movie ID {item.manager_id} from Radarr with deleteFiles=true. "
                       f"Local file(s):\n  {local_paths_display}",
            ))
        elif item.manager_kind == "sonarr":
            steps.append(DuplicatesDryRunStep(
                service="Sonarr",
                action="remove_series",
                dry_run=True,
                detail=f"Would delete series ID {item.manager_id} from Sonarr with deleteFiles=true. "
                       f"Local episode files ({len(item.local_paths)} file(s)) will be removed.",
            ))
        else:
            warnings.append(
                "No Radarr/Sonarr manager linked — cannot safely delete local copy via manager."
            )
            steps.append(DuplicatesDryRunStep(
                service="Plex",
                action="remove_local_version",
                dry_run=True,
                detail=f"Would use Plex API to remove local version(s):\n  {local_paths_display}",
            ))

        steps.append(DuplicatesDryRunStep(
            service="Plex",
            action="refresh_library",
            dry_run=True,
            detail=f"Would refresh Plex library '{item.library}' — NAS copy will remain available.",
        ))
        steps.append(DuplicatesDryRunStep(
            service="Local DB",
            action="update_file_paths",
            dry_run=True,
            detail="Would update local cache to remove local file path entries for this item.",
        ))

        nas_display = "\n  ".join(item.nas_paths)
        steps.append(DuplicatesDryRunStep(
            service="Info",
            action="nas_copy_retained",
            dry_run=True,
            detail=f"NAS copy will be KEPT (protected path):\n  {nas_display}",
        ))

        plan_items.append(DuplicatesDryRunItem(
            media_item_id=item.id,
            title=item.title,
            library=item.library,
            manager_kind=item.manager_kind,
            local_paths=item.local_paths,
            nas_paths=item.nas_paths,
            reclaimable_bytes=item.file_size_bytes,
            steps=steps,
            warnings=warnings,
        ))

    total_reclaimable = sum(i.reclaimable_bytes for i in plan_items)
    return DuplicatesDryRunPlan(
        items=plan_items,
        total_reclaimable_bytes=total_reclaimable,
        global_warnings=global_warnings,
    )
