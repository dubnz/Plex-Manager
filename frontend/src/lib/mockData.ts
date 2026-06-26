import type { DeletePreviewPlan, MediaItem, StatusResponse } from "../types";

export const mockStatus: StatusResponse = {
  demo_mode: true,
  sync_interval_minutes: 60,
  selected_libraries: ["Movies", "TV Shows"],
  integrations: [
    { name: "Plex", state: "demo", detail: "Demo data mode." },
    { name: "Tautulli", state: "demo", detail: "Demo data mode." },
    { name: "Radarr", state: "demo", detail: "Demo data mode." },
    { name: "Sonarr", state: "demo", detail: "Demo data mode." },
    { name: "Seerr", state: "demo", detail: "Demo data mode." }
  ]
};

export const mockMedia: MediaItem[] = [
  {
    id: 1,
    plex_rating_key: "1001",
    library: "Movies",
    media_type: "movie",
    title: "Arrival",
    year: 2016,
    added_at: "2023-01-18T09:15:00+00:00",
    play_count: 4,
    last_played: "2025-10-05T19:30:00+00:00",
    watched_by: ["Kyle", "Sam"],
    requested_by: "Sam",
    request_date: "2023-01-12T10:00:00+00:00",
    manager_kind: "radarr",
    manager_id: 41,
    available: true,
    file_size_bytes: 8734003200,
    file_paths: []
  },
  {
    id: 2,
    plex_rating_key: "1002",
    library: "Movies",
    media_type: "movie",
    title: "The Vast of Night",
    year: 2019,
    added_at: "2023-02-02T12:20:00+00:00",
    play_count: 0,
    last_played: null,
    watched_by: [],
    requested_by: "Alex",
    request_date: "2023-01-27T08:00:00+00:00",
    manager_kind: "radarr",
    manager_id: 88,
    available: true,
    file_size_bytes: 5368709120,
    file_paths: []
  },
  {
    id: 3,
    plex_rating_key: "2001",
    library: "TV Shows",
    media_type: "show",
    title: "The Expanse",
    year: 2015,
    added_at: "2022-11-01T21:12:00+00:00",
    play_count: 26,
    last_played: "2026-02-20T06:45:00+00:00",
    watched_by: ["Kyle"],
    requested_by: "Kyle",
    request_date: "2022-10-28T16:25:00+00:00",
    manager_kind: "sonarr",
    manager_id: 12,
    available: true,
    file_size_bytes: 192414534656,
    file_paths: []
  },
  {
    id: 4,
    plex_rating_key: "2002",
    library: "TV Shows",
    media_type: "show",
    title: "Counterpart",
    year: 2017,
    added_at: "2023-05-28T04:18:00+00:00",
    play_count: 0,
    last_played: null,
    watched_by: [],
    requested_by: null,
    request_date: null,
    manager_kind: "sonarr",
    manager_id: 59,
    available: false,
    file_size_bytes: 64424509440,
    file_paths: []
  }
];

export function buildMockPreview(items: MediaItem[]): DeletePreviewPlan {
  return {
    requires_confirmation: true,
    storage_reclaim_estimate_bytes: items.reduce((sum, item) => sum + item.file_size_bytes, 0),
    global_warnings: [
      "Preview only: no destructive action has been performed.",
      "Demo preview generated locally because the API is unavailable."
    ],
    items: items.map((item) => ({
      media_item_id: item.id,
      title: item.title,
      library: item.library,
      manager_kind: item.manager_kind,
      file_size_bytes: item.file_size_bytes,
      warnings: [],
      steps: [
        {
          service: item.manager_kind === "sonarr" ? "Sonarr" : "Radarr",
          action: item.manager_kind === "sonarr" ? "delete_series" : "delete_movie",
          simulated: true,
          detail: `Would delete ${item.title} with files after explicit confirmation.`
        },
        {
          service: "Seerr",
          action: "mark_unavailable",
          simulated: true,
          detail: "Would mark unavailable only after the manager delete succeeds."
        },
        {
          service: "Plex",
          action: "refresh_library",
          simulated: true,
          detail: "Would refresh the selected Plex section."
        }
      ]
    }))
  };
}

