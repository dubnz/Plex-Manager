from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import db
from app.core.config import Settings, load_settings
from app.models import (
    ConnectionValidationResponse,
    DeleteDryRunPlan,
    DeleteDryRunRequest,
    DeleteExecuteRequest,
    DeleteExecuteResponse,
    DuplicatesListResponse,
    DuplicatesDryRunPlan,
    DuplicatesDryRunRequest,
    MediaListResponse,
    ServiceConfigResponse,
    ServiceConfigUpdate,
    StatusResponse,
    SyncRunResponse,
)
from app.services.cleanup import build_delete_dry_run_plan, execute_delete_plan
from app.services.configuration import public_config, save_config
from app.services.duplicates import build_duplicates_dry_run_plan
from app.services.status import build_integration_status
from app.services.sync import run_sync
from app.services.validation import validate_connections


router = APIRouter(prefix="/api")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_connection(request: Request) -> sqlite3.Connection:
    return request.app.state.db


@router.get("/status", response_model=StatusResponse)
def status(settings: Settings = Depends(get_settings)) -> StatusResponse:
    return StatusResponse(
        demo_mode=settings.demo_mode,
        integrations=build_integration_status(settings),
        sync_interval_minutes=settings.sync_interval_minutes,
        selected_libraries=list(settings.plex_library_names),
    )


@router.get("/config", response_model=ServiceConfigResponse)
def config(settings: Settings = Depends(get_settings)) -> ServiceConfigResponse:
    return public_config(settings)


@router.put("/config", response_model=ServiceConfigResponse)
def update_config(
    update: ServiceConfigUpdate,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ServiceConfigResponse:
    save_config(settings, update)
    request.app.state.settings = load_settings()
    return public_config(request.app.state.settings)


@router.post("/config/validate", response_model=ConnectionValidationResponse)
async def validate_config(settings: Settings = Depends(get_settings)) -> ConnectionValidationResponse:
    return await validate_connections(settings)


@router.get("/media", response_model=MediaListResponse)
def media(
    library: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> MediaListResponse:
    if library and library not in settings.plex_library_names:
        raise HTTPException(status_code=400, detail=f"Library '{library}' is not selected for Plex Media Manager.")
    items = db.list_media(conn, library=library)
    return MediaListResponse(items=items, total=len(items), demo_mode=settings.demo_mode)


@router.post("/actions/delete/dry-run", response_model=DeleteDryRunPlan)
def delete_dry_run(
    request: DeleteDryRunRequest,
    conn: sqlite3.Connection = Depends(get_connection),
) -> DeleteDryRunPlan:
    items = db.get_media_by_ids(conn, request.media_item_ids)
    found_ids = {item.id for item in items}
    missing_ids = [item_id for item_id in request.media_item_ids if item_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Unknown media item ids: {missing_ids}")
    return build_delete_dry_run_plan(items, delete_files=request.delete_files)


@router.post("/actions/delete/execute", response_model=DeleteExecuteResponse)
async def delete_execute(
    request: DeleteExecuteRequest,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> DeleteExecuteResponse:
    items = db.get_media_by_ids(conn, request.media_item_ids)
    found_ids = {item.id for item in items}
    missing_ids = [item_id for item_id in request.media_item_ids if item_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Unknown media item ids: {missing_ids}")
    try:
        return await execute_delete_plan(
            settings,
            conn,
            items,
            delete_files=request.delete_files,
            confirmation=request.confirmation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync/run", response_model=SyncRunResponse)
async def sync_run(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> SyncRunResponse:
    return await run_sync(settings, conn)


@router.get("/duplicates", response_model=DuplicatesListResponse)
def duplicates_list(
    library: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> DuplicatesListResponse:
    items = db.list_duplicates(
        conn,
        local_prefixes=settings.local_media_paths,
        protected_prefixes=settings.protected_media_paths,
        library=library,
    )
    total_reclaimable = sum(item.file_size_bytes for item in items)
    return DuplicatesListResponse(
        items=items,
        total=len(items),
        total_reclaimable_bytes=total_reclaimable,
        demo_mode=settings.demo_mode,
    )


@router.post("/duplicates/dry-run", response_model=DuplicatesDryRunPlan)
def duplicates_dry_run(
    request: DuplicatesDryRunRequest,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> DuplicatesDryRunPlan:
    all_dupes = db.list_duplicates(
        conn,
        local_prefixes=settings.local_media_paths,
        protected_prefixes=settings.protected_media_paths,
    )
    dupes_by_id = {item.id: item for item in all_dupes}
    missing = [item_id for item_id in request.media_item_ids if item_id not in dupes_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown or non-duplicate item ids: {missing}")
    selected = [dupes_by_id[item_id] for item_id in request.media_item_ids]
    return build_duplicates_dry_run_plan(selected)
