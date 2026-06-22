import { Archive, Database, Download, RefreshCw, Search, ShieldCheck, Tags, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createDeleteDryRun, getMedia, getStatus } from "./api";
import { buildMockDryRun, mockMedia, mockStatus } from "./lib/mockData";
import { filterMedia, toCsv } from "./lib/filters";
import { formatBytes, formatDate } from "./lib/format";
import type { DeleteDryRunPlan, FilterState, LibraryName, MediaItem, StatusResponse } from "./types";

const LIBRARIES: LibraryName[] = ["Movies", "TV Shows"];

export function App() {
  const [activeLibrary, setActiveLibrary] = useState<LibraryName>("Movies");
  const [status, setStatus] = useState<StatusResponse>(mockStatus);
  const [items, setItems] = useState<MediaItem[]>(mockMedia);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [dryRunPlan, setDryRunPlan] = useState<DeleteDryRunPlan | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    quickFilter: "all",
    availability: "all",
    minPlayCount: 0
  });
  const [apiNote, setApiNote] = useState("Loading API status...");

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const [nextStatus, media] = await Promise.all([getStatus(), getMedia(activeLibrary)]);
        if (!ignore) {
          setStatus(nextStatus);
          setItems(media.items);
          setApiNote(nextStatus.demo_mode ? "Demo mode from backend" : "Connected to backend cache");
        }
      } catch (error) {
        if (!ignore) {
          setStatus(mockStatus);
          setItems(mockMedia.filter((item) => item.library === activeLibrary));
          setApiNote("API unavailable; using local demo data");
        }
      }
    }

    load();
    setSelectedIds(new Set());
    setDryRunPlan(null);
    return () => {
      ignore = true;
    };
  }, [activeLibrary]);

  const visibleItems = useMemo(() => filterMedia(items, filters), [items, filters]);
  const selectedItems = useMemo(
    () => visibleItems.filter((item) => selectedIds.has(item.id)),
    [selectedIds, visibleItems]
  );
  const allVisibleSelected = visibleItems.length > 0 && visibleItems.every((item) => selectedIds.has(item.id));

  async function runDryDelete() {
    if (selectedIds.size === 0) return;
    const ids = [...selectedIds];
    try {
      setDryRunPlan(await createDeleteDryRun(ids));
    } catch {
      setDryRunPlan(buildMockDryRun(visibleItems.filter((item) => selectedIds.has(item.id))));
    }
  }

  function exportSelection() {
    const csv = toCsv(selectedItems.length ? selectedItems : visibleItems);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `plex-manager-${activeLibrary.toLowerCase().replace(/\s+/g, "-")}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function toggleVisibleSelection() {
    if (allVisibleSelected) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(visibleItems.map((item) => item.id)));
  }

  function toggleItem(id: number) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Database size={20} />
          </div>
          <div>
            <strong>Plex Manager</strong>
            <span>{apiNote}</span>
          </div>
        </div>

        <nav className="library-tabs" aria-label="Libraries">
          {LIBRARIES.map((library) => (
            <button
              key={library}
              className={library === activeLibrary ? "active" : ""}
              onClick={() => setActiveLibrary(library)}
            >
              {library}
            </button>
          ))}
        </nav>

        <div className="status-stack">
          {status.integrations.map((integration) => (
            <div className="status-row" key={integration.name} title={integration.detail}>
              <span className={`status-dot ${integration.state}`} />
              <span>{integration.name}</span>
              <small>{integration.state}</small>
            </div>
          ))}
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{activeLibrary}</h1>
            <p>Oldest added first. Exact sections only: {status.selected_libraries.join(", ")}.</p>
          </div>
          <button className="icon-button" title="Run sync">
            <RefreshCw size={17} />
            Sync
          </button>
        </header>

        <section className="toolbar" aria-label="Filters and batch actions">
          <label className="search-box">
            <Search size={17} />
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search title, year, requester, watcher"
            />
          </label>

          <div className="segmented">
            <button
              className={filters.quickFilter === "all" ? "active" : ""}
              onClick={() => setFilters((current) => ({ ...current, quickFilter: "all" }))}
            >
              All
            </button>
            <button
              className={filters.quickFilter === "never-watched" ? "active" : ""}
              onClick={() => setFilters((current) => ({ ...current, quickFilter: "never-watched" }))}
            >
              Never watched
            </button>
            <button
              className={filters.quickFilter === "watched-by-no-one" ? "active" : ""}
              onClick={() => setFilters((current) => ({ ...current, quickFilter: "watched-by-no-one" }))}
            >
              Watched by no one
            </button>
          </div>

          <select
            value={filters.availability}
            onChange={(event) =>
              setFilters((current) => ({ ...current, availability: event.target.value as FilterState["availability"] }))
            }
          >
            <option value="all">Any status</option>
            <option value="available">Available</option>
            <option value="unavailable">Unavailable</option>
          </select>

          <div className="action-group">
            <button className="danger" disabled={!selectedIds.size} onClick={runDryDelete}>
              <Trash2 size={16} />
              Dry-run delete
            </button>
            <button disabled={!selectedIds.size}>
              <Tags size={16} />
              Mark unavailable
            </button>
            <button disabled={!selectedIds.size}>
              <Archive size={16} />
              Archive/tag
            </button>
            <button onClick={exportSelection}>
              <Download size={16} />
              Export CSV
            </button>
          </div>
        </section>

        <div className="content-grid">
          <section className="table-panel" aria-label={`${activeLibrary} media`}>
            <div className="table-summary">
              <span>{visibleItems.length} filtered</span>
              <span>{selectedIds.size} selected</span>
              <span>{formatBytes(visibleItems.reduce((sum, item) => sum + item.file_size_bytes, 0))} visible</span>
            </div>

            <table>
              <thead>
                <tr>
                  <th className="select-cell">
                    <input type="checkbox" checked={allVisibleSelected} onChange={toggleVisibleSelection} />
                  </th>
                  <th>Title</th>
                  <th>Added</th>
                  <th>Plays</th>
                  <th>Last played</th>
                  <th>Requested by</th>
                  <th>Watched by</th>
                  <th>Status</th>
                  <th>Size</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => (
                  <tr key={item.id} className={selectedIds.has(item.id) ? "selected-row" : ""}>
                    <td className="select-cell">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleItem(item.id)}
                      />
                    </td>
                    <td>
                      <strong>{item.title}</strong>
                      <span>{item.year ?? "Unknown"} · {item.manager_kind}</span>
                    </td>
                    <td>{formatDate(item.added_at)}</td>
                    <td>{item.play_count}</td>
                    <td>{formatDate(item.last_played)}</td>
                    <td>{item.requested_by ?? "Unknown"}</td>
                    <td>{item.watched_by.length ? item.watched_by.join(", ") : "No one"}</td>
                    <td>
                      <span className={`availability ${item.available ? "available" : "unavailable"}`}>
                        {item.available ? "Available" : "Unavailable"}
                      </span>
                    </td>
                    <td>{formatBytes(item.file_size_bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <aside className="preview-panel" aria-label="Delete preview">
            <div className="preview-heading">
              <ShieldCheck size={19} />
              <div>
                <h2>Delete preview</h2>
                <p>No destructive action will run until confirmed.</p>
              </div>
            </div>

            {dryRunPlan ? (
              <div className="dry-run">
                <div className="estimate">
                  <span>Storage reclaim estimate</span>
                  <strong>{formatBytes(dryRunPlan.storage_reclaim_estimate_bytes)}</strong>
                </div>
                {dryRunPlan.global_warnings.map((warning) => (
                  <p className="warning" key={warning}>{warning}</p>
                ))}
                {dryRunPlan.items.map((item) => (
                  <div className="plan-item" key={item.media_item_id}>
                    <strong>{item.title}</strong>
                    <span>{item.library} · {item.manager_kind}</span>
                    <ol>
                      {item.steps.map((step) => (
                        <li key={`${item.media_item_id}-${step.service}-${step.action}`}>
                          <b>{step.service}</b>
                          <small>{step.detail}</small>
                        </li>
                      ))}
                    </ol>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-preview">
                <Trash2 size={28} />
                <p>Select media and run a dry-run delete to see the exact Sonarr/Radarr, Seerr, Plex, and local DB steps.</p>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
