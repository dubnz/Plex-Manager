from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MediaType = Literal["movie", "show"]
LibraryName = Literal["Movies", "TV Shows"]


class IntegrationStatus(BaseModel):
    name: str
    state: Literal["ok", "demo", "missing", "error", "blocked"]
    detail: str


class MediaItem(BaseModel):
    id: int
    plex_rating_key: str
    library: str
    media_type: MediaType
    title: str
    year: int | None = None
    added_at: datetime
    play_count: int = 0
    last_played: datetime | None = None
    watched_by: list[str] = Field(default_factory=list)
    requested_by: str | None = None
    request_date: datetime | None = None
    manager_kind: Literal["radarr", "sonarr", "none"] = "none"
    manager_id: int | None = None
    available: bool = True
    file_size_bytes: int = 0


class MediaListResponse(BaseModel):
    items: list[MediaItem]
    total: int
    demo_mode: bool


class DeleteDryRunRequest(BaseModel):
    media_item_ids: list[int] = Field(min_length=1)
    delete_files: bool = True


class DeleteDryRunStep(BaseModel):
    service: str
    action: str
    dry_run: bool = True
    detail: str


class DeleteDryRunItem(BaseModel):
    media_item_id: int
    title: str
    library: str
    manager_kind: str
    file_size_bytes: int
    steps: list[DeleteDryRunStep]
    warnings: list[str] = Field(default_factory=list)


class DeleteDryRunPlan(BaseModel):
    items: list[DeleteDryRunItem]
    storage_reclaim_estimate_bytes: int
    requires_confirmation: bool = True
    global_warnings: list[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    demo_mode: bool
    integrations: list[IntegrationStatus]
    sync_interval_minutes: int
    selected_libraries: list[str]

