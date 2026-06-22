from __future__ import annotations

from app.models import DeleteDryRunItem, DeleteDryRunPlan, DeleteDryRunStep, MediaItem


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
            "Dry-run only: no destructive action has been performed.",
            "Real delete remains blocked until authenticated reads and explicit confirmation are verified.",
        ],
    )

