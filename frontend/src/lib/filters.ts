import type { FilterState, MediaItem } from "../types";

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
      return true;
    })
    .slice()
    .sort((a, b) => new Date(a.added_at).getTime() - new Date(b.added_at).getTime());
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
