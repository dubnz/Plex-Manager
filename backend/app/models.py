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


class SyncRunResponse(BaseModel):
    status: str
    detail: str
    synced_items: int = 0
    selected_libraries: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ServiceConfigResponse(BaseModel):
    plex_url: str
    plex_token_set: bool
    plex_token_placeholder: bool
    plex_library_names: list[str]
    tautulli_url: str
    tautulli_api_key_set: bool
    tautulli_api_key_placeholder: bool
    sonarr_url: str
    sonarr_api_key_set: bool
    sonarr_api_key_placeholder: bool
    radarr_url: str
    radarr_api_key_set: bool
    radarr_api_key_placeholder: bool
    seerr_kind: str
    seerr_url: str
    seerr_api_key_set: bool
    seerr_api_key_placeholder: bool
    legacy_seerr_url: str
    legacy_seerr_api_key_set: bool
    legacy_seerr_api_key_placeholder: bool
    sync_interval_minutes: int
    config_path: str


class ServiceConfigUpdate(BaseModel):
    plex_url: str
    plex_token: str | None = None
    plex_library_names: list[str] = Field(min_length=1)
    tautulli_url: str
    tautulli_api_key: str | None = None
    sonarr_url: str
    sonarr_api_key: str | None = None
    radarr_url: str
    radarr_api_key: str | None = None
    seerr_kind: Literal["overseerr", "jellyseerr"]
    seerr_url: str
    seerr_api_key: str | None = None
    legacy_seerr_url: str = ""
    legacy_seerr_api_key: str | None = None
    sync_interval_minutes: int = Field(ge=5, le=1440)


class ConnectionValidationResponse(BaseModel):
    integrations: list[IntegrationStatus]
