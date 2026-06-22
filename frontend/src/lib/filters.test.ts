import { describe, expect, it } from "vitest";
import { filterMedia, toCsv } from "./filters";
import { mockMedia } from "./mockData";

describe("filterMedia", () => {
  it("defaults to oldest added first", () => {
    const result = filterMedia(mockMedia, {
      search: "",
      quickFilter: "all",
      availability: "all",
      minPlayCount: 0
    });

    expect(result[0].title).toBe("The Expanse");
  });

  it("filters never watched items", () => {
    const result = filterMedia(mockMedia, {
      search: "",
      quickFilter: "never-watched",
      availability: "all",
      minPlayCount: 0
    });

    expect(result.map((item) => item.title)).toEqual(["The Vast of Night", "Counterpart"]);
  });
});

describe("toCsv", () => {
  it("exports selected rows", () => {
    const csv = toCsv([mockMedia[0]]);
    expect(csv).toContain("Arrival");
    expect(csv.split("\n")).toHaveLength(2);
  });
});

