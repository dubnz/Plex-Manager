from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import db
from app.core.config import Settings, load_settings
from app.models import (
    ConnectionValidationResponse,
    DeleteDryRunPlan,
    DeleteDryRunRequest,
    MediaListResponse,
    ServiceConfigResponse,
    ServiceConfigUpdate,
    StatusResponse,
    SyncRunResponse,
)
from app.services.cleanup import build_delete_dry_run_plan
from app.services.configuration import public_config, save_config
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
        raise HTTPException(status_code=400, detail=f"Library '{library}' is not selected for Plex Manager.")
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

@router.post("/sync/run", response_model=SyncRunResponse)
async def sync_run(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_connection),
) -> SyncRunResponse:
    return await run_sync(settings, conn)
