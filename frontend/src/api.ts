import type { DeleteDryRunPlan, MediaListResponse, StatusResponse } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getStatus(): Promise<StatusResponse> {
  return getJson<StatusResponse>("/api/status");
}

export async function getMedia(library: string): Promise<MediaListResponse> {
  const params = new URLSearchParams({ library });
  return getJson<MediaListResponse>(`/api/media?${params.toString()}`);
}

export async function createDeleteDryRun(ids: number[], deleteFiles = true): Promise<DeleteDryRunPlan> {
  const response = await fetch("/api/actions/delete/dry-run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media_item_ids: ids, delete_files: deleteFiles })
  });
  if (!response.ok) {
    throw new Error(`Dry-run failed with ${response.status}`);
  }
  return response.json() as Promise<DeleteDryRunPlan>;
}

