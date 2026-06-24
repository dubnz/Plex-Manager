import type {
  ConnectionValidationResponse,
  DeleteDryRunPlan,
  MediaListResponse,
  ServiceConfigResponse,
  ServiceConfigUpdate,
  StatusResponse
} from "./types";

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

export async function getConfig(): Promise<ServiceConfigResponse> {
  return getJson<ServiceConfigResponse>("/api/config");
}

export async function saveConfig(config: ServiceConfigUpdate): Promise<ServiceConfigResponse> {
  const response = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    throw new Error(`Save config failed with ${response.status}`);
  }
  return response.json() as Promise<ServiceConfigResponse>;
}

export async function validateConfig(): Promise<ConnectionValidationResponse> {
  const response = await fetch("/api/config/validate", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Validate config failed with ${response.status}`);
  }
  return response.json() as Promise<ConnectionValidationResponse>;
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
