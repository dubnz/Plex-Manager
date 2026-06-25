import { describe, expect, it } from "vitest";
import { filterMedia, toCsv } from "./filters";
import { mockMedia } from "./mockData";
import type { FilterState } from "../types";

function filters(overrides: Partial<FilterState> = {}): FilterState {
  return {
    search: "",
    quickFilter: "all",
    availability: "all",
    minPlayCount: 0,
    columnFilters: {
      title: "",
      added_at: "",
      play_count: "",
      last_played: "",
      requested_by: "",
      watched_by: "",
      available: "all",
      file_size_bytes: "",
    },
    sort: { key: "added_at", direction: "asc" },
    ...overrides,
  };
}

describe("filterMedia", () => {
  it("defaults to oldest added first", () => {
    const result = filterMedia(mockMedia, filters());

    expect(result[0].title).toBe("The Expanse");
  });

  it("filters never watched items", () => {
    const result = filterMedia(mockMedia, filters({ quickFilter: "never-watched" }));

    expect(result.map((item) => item.title)).toEqual(["The Vast of Night", "Counterpart"]);
  });

  it("filters by a specific table column", () => {
    const result = filterMedia(
      mockMedia,
      filters({
        columnFilters: {
          title: "",
          added_at: "",
          play_count: "",
          last_played: "",
          requested_by: "alex",
          watched_by: "",
          available: "all",
          file_size_bytes: "",
        },
      })
    );

    expect(result.map((item) => item.title)).toEqual(["The Vast of Night"]);
  });

  it("sorts by any configured column", () => {
    const result = filterMedia(mockMedia, filters({ sort: { key: "file_size_bytes", direction: "desc" } }));

    expect(result[0].title).toBe("The Expanse");
  });
});

describe("toCsv", () => {
  it("exports selected rows", () => {
    const csv = toCsv([mockMedia[0]]);
    expect(csv).toContain("Arrival");
    expect(csv.split("\n")).toHaveLength(2);
  });
});
