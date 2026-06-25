import type { FilterState, MediaItem, SortKey } from "../types";
import { formatBytes, formatDate } from "./format";

export function filterMedia(items: MediaItem[], filters: FilterState): MediaItem[] {
  const search = filters.search.trim().toLowerCase();
  return items
    .filter((item) => {
      if (search) {
        const haystack = `${item.title} ${item.year ?? ""} ${item.requested_by ?? ""} ${item.watched_by.join(" ")}`;
        if (!haystack.toLowerCase().includes(search)) return false;
      }
      if (filters.quickFilter === "never-watched" && item.play_count !== 0) return false;
      if (filters.quickFilter === "watched-by-no-one" && item.watched_by.length > 0) return false;
      if (filters.availability === "available" && !item.available) return false;
      if (filters.availability === "unavailable" && item.available) return false;
      if (item.play_count < filters.minPlayCount) return false;
      if (!matchesColumnFilters(item, filters)) return false;
      return true;
    })
    .slice()
    .sort((a, b) => compareMedia(a, b, filters.sort.key, filters.sort.direction));
}

function matchesColumnFilters(item: MediaItem, filters: FilterState): boolean {
  const columnFilters = filters.columnFilters;
  if (columnFilters.available !== "all") {
    if (columnFilters.available === "available" && !item.available) return false;
    if (columnFilters.available === "unavailable" && item.available) return false;
  }

  return (Object.keys(columnFilters) as Array<keyof typeof columnFilters>).every((key) => {
    if (key === "available") return true;
    const needle = String(columnFilters[key]).trim().toLowerCase();
    if (!needle) return true;
    return columnFilterValue(item, key).includes(needle);
  });
}

function columnFilterValue(item: MediaItem, key: Exclude<SortKey, "available">): string {
  switch (key) {
    case "title":
      return `${item.title} ${item.year ?? ""} ${item.manager_kind}`.toLowerCase();
    case "added_at":
      return `${formatDate(item.added_at)} ${item.added_at}`.toLowerCase();
    case "play_count":
      return String(item.play_count);
    case "last_played":
      return `${formatDate(item.last_played)} ${item.last_played ?? ""}`.toLowerCase();
    case "requested_by":
      return (item.requested_by ?? "unknown").toLowerCase();
    case "watched_by":
      return (item.watched_by.length ? item.watched_by.join(" ") : "no one").toLowerCase();
    case "file_size_bytes":
      return `${formatBytes(item.file_size_bytes)} ${item.file_size_bytes}`.toLowerCase();
  }
}

function compareMedia(a: MediaItem, b: MediaItem, key: SortKey, direction: "asc" | "desc"): number {
  const modifier = direction === "asc" ? 1 : -1;
  const result = compareSortValues(sortValue(a, key), sortValue(b, key));
  if (result !== 0) return result * modifier;
  return a.title.localeCompare(b.title) * modifier;
}

function sortValue(item: MediaItem, key: SortKey): string | number {
  switch (key) {
    case "title":
      return item.title.toLowerCase();
    case "added_at":
      return new Date(item.added_at).getTime();
    case "play_count":
      return item.play_count;
    case "last_played":
      return item.last_played ? new Date(item.last_played).getTime() : 0;
    case "requested_by":
      return (item.requested_by ?? "").toLowerCase();
    case "watched_by":
      return item.watched_by.join(" ").toLowerCase();
    case "available":
      return item.available ? 1 : 0;
    case "file_size_bytes":
      return item.file_size_bytes;
  }
}

function compareSortValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function toCsv(items: MediaItem[]): string {
  const headers = [
    "library",
    "title",
    "year",
    "added_at",
    "play_count",
    "last_played",
    "requested_by",
    "watched_by",
    "available",
    "file_size_bytes"
  ];
  const rows = items.map((item) =>
    [
      item.library,
      item.title,
      item.year ?? "",
      item.added_at,
      item.play_count,
      item.last_played ?? "",
      item.requested_by ?? "",
      item.watched_by.join("; "),
      item.available ? "available" : "unavailable",
      item.file_size_bytes
    ]
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(",")
  );
  return [headers.join(","), ...rows].join("\n");
}
