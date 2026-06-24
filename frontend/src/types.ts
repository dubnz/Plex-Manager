export type LibraryName = "Movies" | "TV Shows";
export type MediaType = "movie" | "show";
export type IntegrationState = "ok" | "demo" | "missing" | "error" | "blocked";

export interface IntegrationStatus {
  name: string;
  state: IntegrationState;
  detail: string;
}

export interface StatusResponse {
  demo_mode: boolean;
  integrations: IntegrationStatus[];
  sync_interval_minutes: number;
  selected_libraries: string[];
}

export interface ServiceConfigResponse {
  plex_url: string;
  plex_token_set: boolean;
  plex_token_placeholder: boolean;
  plex_library_names: string[];
  tautulli_url: string;
  tautulli_api_key_set: boolean;
  tautulli_api_key_placeholder: boolean;
  sonarr_url: string;
  sonarr_api_key_set: boolean;
  sonarr_api_key_placeholder: boolean;
  radarr_url: string;
  radarr_api_key_set: boolean;
  radarr_api_key_placeholder: boolean;
  seerr_kind: "overseerr" | "jellyseerr";
  seerr_url: string;
  seerr_api_key_set: boolean;
  seerr_api_key_placeholder: boolean;
  sync_interval_minutes: number;
  config_path: string;
}

export interface ServiceConfigUpdate {
  plex_url: string;
  plex_token?: string | null;
  plex_library_names: string[];
  tautulli_url: string;
  tautulli_api_key?: string | null;
  sonarr_url: string;
  sonarr_api_key?: string | null;
  radarr_url: string;
  radarr_api_key?: string | null;
  seerr_kind: "overseerr" | "jellyseerr";
  seerr_url: string;
  seerr_api_key?: string | null;
  sync_interval_minutes: number;
}

export interface ConnectionValidationResponse {
  integrations: IntegrationStatus[];
}

export interface SyncRunResponse {
  status: string;
  detail: string;
  synced_items: number;
  selected_libraries: string[];
  warnings: string[];
}

export interface MediaItem {
  id: number;
  plex_rating_key: string;
  library: string;
  media_type: MediaType;
  title: string;
  year: number | null;
  added_at: string;
  play_count: number;
  last_played: string | null;
  watched_by: string[];
  requested_by: string | null;
  request_date: string | null;
  manager_kind: "radarr" | "sonarr" | "none";
  manager_id: number | null;
  available: boolean;
  file_size_bytes: number;
}

export interface MediaListResponse {
  items: MediaItem[];
  total: number;
  demo_mode: boolean;
}

export interface DeleteDryRunStep {
  service: string;
  action: string;
  dry_run: boolean;
  detail: string;
}

export interface DeleteDryRunItem {
  media_item_id: number;
  title: string;
  library: string;
  manager_kind: string;
  file_size_bytes: number;
  steps: DeleteDryRunStep[];
  warnings: string[];
}

export interface DeleteDryRunPlan {
  items: DeleteDryRunItem[];
  storage_reclaim_estimate_bytes: number;
  requires_confirmation: boolean;
  global_warnings: string[];
}

export interface FilterState {
  search: string;
  quickFilter: "all" | "never-watched" | "watched-by-no-one";
  availability: "all" | "available" | "unavailable";
  minPlayCount: number;
}
