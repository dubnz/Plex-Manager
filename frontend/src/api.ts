import type {
  ConnectionValidationResponse,
  DeleteExecuteResponse,
  DeletePreviewPlan,
  DuplicatesListResponse,
  DuplicatesPreviewPlan,
  DuplicatesExecuteResponse,
  MediaListResponse,
  ServiceConfigResponse,
  ServiceConfigUpdate,
  StatusResponse,
  SyncRunResponse
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

export async function runSync(): Promise<SyncRunResponse> {
  const response = await fetch("/api/sync/run", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Sync failed with ${response.status}`);
  }
  return response.json() as Promise<SyncRunResponse>;
}

export async function createDeletePreview(ids: number[], deleteFiles = true): Promise<DeletePreviewPlan> {
  const response = await fetch("/api/actions/delete/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media_item_ids: ids, delete_files: deleteFiles })
  });
  if (!response.ok) {
    throw new Error(`Preview failed with ${response.status}`);
  }
  return response.json() as Promise<DeletePreviewPlan>;
}

export async function executeDelete(
  ids: number[],
  confirmation: string,
  deleteFiles = true
): Promise<DeleteExecuteResponse> {
  const response = await fetch("/api/actions/delete/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media_item_ids: ids, delete_files: deleteFiles, confirmation })
  });
  if (!response.ok) {
    throw new Error(`Delete failed with ${response.status}`);
  }
  return response.json() as Promise<DeleteExecuteResponse>;
}

export async function getDuplicates(library?: string): Promise<DuplicatesListResponse> {
  const params = library ? new URLSearchParams({ library }) : new URLSearchParams();
  const qs = params.toString() ? `?${params.toString()}` : "";
  return getJson<DuplicatesListResponse>(`/api/duplicates${qs}`);
}

export async function createDuplicatesPreview(ids: number[]): Promise<DuplicatesPreviewPlan> {
  const response = await fetch("/api/duplicates/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media_item_ids: ids })
  });
  if (!response.ok) {
    throw new Error(`Duplicates preview failed with ${response.status}`);
  }
  return response.json() as Promise<DuplicatesPreviewPlan>;
}

export async function executeDuplicates(ids: number[]): Promise<DuplicatesExecuteResponse> {
  const response = await fetch("/api/duplicates/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media_item_ids: ids })
  });
  if (!response.ok) {
    throw new Error(`Delete failed with ${response.status}`);
  }
  return response.json() as Promise<DuplicatesExecuteResponse>;
}
