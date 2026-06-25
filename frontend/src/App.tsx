import {
  Archive,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Copy,
  Download,
  KeyRound,
  PanelRightOpen,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Tags,
  Trash2,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { createDeleteDryRun, createDuplicatesDryRun, executeDelete, getConfig, getDuplicates, getMedia, getStatus, runSync, saveConfig, validateConfig } from "./api";
import { buildMockDryRun, mockMedia, mockStatus } from "./lib/mockData";
import { filterMedia, toCsv } from "./lib/filters";
import { formatBytes, formatDate } from "./lib/format";
import type {
  ConnectionValidationResponse,
  DeleteExecuteResponse,
  DeleteDryRunPlan,
  DuplicateItem,
  DuplicatesListResponse,
  DuplicatesDryRunPlan,
  FilterState,
  MediaItem,
  ServiceConfigResponse,
  ServiceConfigUpdate,
  SortKey,
  StatusResponse
} from "./types";

const FALLBACK_LIBRARIES = ["Movies", "TV Shows"];
const DEFAULT_COLUMN_FILTERS = {
  title: "",
  added_at: "",
  play_count: "",
  last_played: "",
  requested_by: "",
  watched_by: "",
  available: "all" as const,
  file_size_bytes: ""
};
const DEFAULT_FILTERS: FilterState = {
  search: "",
  quickFilter: "all",
  availability: "all",
  minPlayCount: 0,
  columnFilters: DEFAULT_COLUMN_FILTERS,
  sort: { key: "added_at", direction: "asc" }
};
const SORTABLE_COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: "title", label: "Title" },
  { key: "added_at", label: "Added" },
  { key: "play_count", label: "Plays" },
  { key: "last_played", label: "Last played" },
  { key: "requested_by", label: "Requested by" },
  { key: "watched_by", label: "Watched by" },
  { key: "available", label: "Status" },
  { key: "file_size_bytes", label: "Size" }
];

type View = "media" | "duplicates" | "settings";

interface ConfigForm {
  plex_url: string;
  plex_token: string;
  plex_library_names: string;
  tautulli_url: string;
  tautulli_api_key: string;
  sonarr_url: string;
  sonarr_api_key: string;
  radarr_url: string;
  radarr_api_key: string;
  seerr_kind: "overseerr" | "jellyseerr";
  seerr_url: string;
  seerr_api_key: string;
  legacy_seerr_url: string;
  legacy_seerr_api_key: string;
  sync_interval_minutes: number;
}

export function App() {
  const [activeLibrary, setActiveLibrary] = useState("Movies");
  const [activeView, setActiveView] = useState<View>("media");
  const [status, setStatus] = useState<StatusResponse>(mockStatus);
  const [items, setItems] = useState<MediaItem[]>(mockMedia);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [dryRunPlan, setDryRunPlan] = useState<DeleteDryRunPlan | null>(null);
  const [deleteResult, setDeleteResult] = useState<DeleteExecuteResponse | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [apiNote, setApiNote] = useState("Loading API status...");
  const [syncMessage, setSyncMessage] = useState("");
  const libraries = status.selected_libraries.length ? status.selected_libraries : FALLBACK_LIBRARIES;

  async function loadMedia(library = activeLibrary) {
    try {
      const [nextStatus, media] = await Promise.all([getStatus(), getMedia(library)]);
          setStatus(nextStatus);
          setItems(media.items);
          setApiNote(nextStatus.demo_mode ? "Demo mode from backend" : "Connected to backend cache");
          if (!nextStatus.selected_libraries.includes(library) && nextStatus.selected_libraries.length > 0) {
            setActiveLibrary(nextStatus.selected_libraries[0]);
          }
    } catch {
      setStatus(mockStatus);
          setItems(mockMedia.filter((item) => item.library === library));
      setApiNote("API unavailable; using local demo data");
    }
  }

  useEffect(() => {
    loadMedia(activeLibrary);
    setSelectedIds(new Set());
    setDryRunPlan(null);
    setDeleteResult(null);
    setDeleteMessage("");
    setPreviewOpen(false);
  }, [activeLibrary]);

  const visibleItems = useMemo(() => filterMedia(items, filters), [items, filters]);
  const selectedItems = useMemo(
    () => visibleItems.filter((item) => selectedIds.has(item.id)),
    [selectedIds, visibleItems]
  );
  const allVisibleSelected = visibleItems.length > 0 && visibleItems.every((item) => selectedIds.has(item.id));
  const activeColumnFilterCount =
    Object.entries(filters.columnFilters).filter(([key, value]) => key !== "available" && String(value).trim()).length +
    (filters.columnFilters.available === "all" ? 0 : 1);

  async function runDryDelete() {
    if (selectedIds.size === 0) return;
    const ids = [...selectedIds];
    setDeleteResult(null);
    setDeleteMessage("");
    try {
      setDryRunPlan(await createDeleteDryRun(ids));
    } catch {
      setDryRunPlan(buildMockDryRun(visibleItems.filter((item) => selectedIds.has(item.id))));
    }
    setPreviewOpen(true);
  }

  async function executeConfirmedDelete(confirmation: string) {
    if (selectedIds.size === 0) return;
    setDeleteBusy(true);
    setDeleteMessage("Deleting selected media...");
    try {
      const result = await executeDelete([...selectedIds], confirmation);
      setDeleteResult(result);
      setDeleteMessage(`Delete finished for ${result.deleted_count} item(s).`);
      setSelectedIds(new Set());
      await loadMedia(activeLibrary);
    } catch (error) {
      setDeleteMessage(error instanceof Error ? error.message : "Delete failed.");
    } finally {
      setDeleteBusy(false);
    }
  }

  function updateSort(key: SortKey) {
    setFilters((current) => ({
      ...current,
      sort: {
        key,
        direction: current.sort.key === key && current.sort.direction === "asc" ? "desc" : "asc"
      }
    }));
  }

  function updateColumnFilter<K extends keyof FilterState["columnFilters"]>(
    key: K,
    value: FilterState["columnFilters"][K]
  ) {
    setFilters((current) => ({
      ...current,
      columnFilters: {
        ...current.columnFilters,
        [key]: value
      }
    }));
  }

  function resetColumnFilters() {
    setFilters((current) => ({ ...current, columnFilters: DEFAULT_COLUMN_FILTERS }));
  }

  async function syncNow() {
    setSyncMessage("Sync running...");
    try {
      const result = await runSync();
      setSyncMessage(result.detail);
      await loadMedia(activeLibrary);
    } catch (error) {
      setSyncMessage(error instanceof Error ? error.message : "Sync failed.");
    }
  }

  function exportSelection() {
    const csv = toCsv(selectedItems.length ? selectedItems : visibleItems);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `plex-media-manager-${activeLibrary.toLowerCase().replace(/\s+/g, "-")}.csv`;
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
            <img src="/plex-media-manager-icon.svg" alt="" />
          </div>
          <div>
            <strong>Plex Media Manager</strong>
            <span>{apiNote}</span>
          </div>
        </div>

        <nav className="library-tabs" aria-label="Navigation">
          {libraries.map((library) => (
            <button
              key={library}
              className={activeView === "media" && library === activeLibrary ? "active" : ""}
              onClick={() => {
                setActiveView("media");
                setActiveLibrary(library);
              }}
            >
              {library}
            </button>
          ))}
          <button
            className={activeView === "duplicates" ? "active" : ""}
            onClick={() => setActiveView("duplicates")}
          >
            <Copy size={16} />
            Duplicates
          </button>
          <button
            className={activeView === "settings" ? "active" : ""}
            onClick={() => setActiveView("settings")}
          >
            <Settings size={16} />
            Settings
          </button>
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

      {activeView === "settings" ? (
        <SettingsView
          onSaved={async () => {
            const nextStatus = await getStatus();
            setStatus(nextStatus);
            setApiNote(nextStatus.demo_mode ? "Demo mode from backend" : "Connected to backend cache");
          }}
        />
      ) : activeView === "duplicates" ? (
        <DuplicatesView />
      ) : (
        <main className="workspace">
          <header className="topbar">
            <div>
              <h1>{activeLibrary}</h1>
              <p>{syncMessage || `Oldest added first. Exact sections only: ${status.selected_libraries.join(", ")}.`}</p>
            </div>
            <button className="icon-button" title="Run sync" onClick={syncNow}>
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
              {dryRunPlan && !previewOpen ? (
                <button onClick={() => setPreviewOpen(true)}>
                  <PanelRightOpen size={16} />
                  View delete preview
                </button>
              ) : null}
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
                <span>Sorted by {SORTABLE_COLUMNS.find((column) => column.key === filters.sort.key)?.label}</span>
                <span>{activeColumnFilterCount} column filters</span>
                {activeColumnFilterCount > 0 ? (
                  <button className="text-button" onClick={resetColumnFilters}>
                    <SlidersHorizontal size={15} />
                    Clear column filters
                  </button>
                ) : null}
              </div>

              <table>
                <thead>
                  <tr>
                    <th className="select-cell">
                      <input type="checkbox" checked={allVisibleSelected} onChange={toggleVisibleSelection} />
                    </th>
                    {SORTABLE_COLUMNS.map((column) => (
                      <SortableHeader
                        key={column.key}
                        label={column.label}
                        sortKey={column.key}
                        activeSortKey={filters.sort.key}
                        direction={filters.sort.direction}
                        onSort={updateSort}
                      />
                    ))}
                  </tr>
                  <tr className="column-filter-row">
                    <th className="select-cell" />
                    <th>
                      <input
                        aria-label="Filter title"
                        value={filters.columnFilters.title}
                        onChange={(event) => updateColumnFilter("title", event.target.value)}
                        placeholder="Filter title"
                      />
                    </th>
                    <th>
                      <input
                        aria-label="Filter added"
                        value={filters.columnFilters.added_at}
                        onChange={(event) => updateColumnFilter("added_at", event.target.value)}
                        placeholder="Date"
                      />
                    </th>
                    <th>
                      <input
                        aria-label="Filter plays"
                        value={filters.columnFilters.play_count}
                        onChange={(event) => updateColumnFilter("play_count", event.target.value)}
                        placeholder="Plays"
                      />
                    </th>
                    <th>
                      <input
                        aria-label="Filter last played"
                        value={filters.columnFilters.last_played}
                        onChange={(event) => updateColumnFilter("last_played", event.target.value)}
                        placeholder="Last"
                      />
                    </th>
                    <th>
                      <input
                        aria-label="Filter requester"
                        value={filters.columnFilters.requested_by}
                        onChange={(event) => updateColumnFilter("requested_by", event.target.value)}
                        placeholder="Requester"
                      />
                    </th>
                    <th>
                      <input
                        aria-label="Filter watchers"
                        value={filters.columnFilters.watched_by}
                        onChange={(event) => updateColumnFilter("watched_by", event.target.value)}
                        placeholder="Watcher"
                      />
                    </th>
                    <th>
                      <select
                        aria-label="Filter status"
                        value={filters.columnFilters.available}
                        onChange={(event) =>
                          updateColumnFilter(
                            "available",
                            event.target.value as FilterState["columnFilters"]["available"]
                          )
                        }
                      >
                        <option value="all">Any</option>
                        <option value="available">Available</option>
                        <option value="unavailable">Unavailable</option>
                      </select>
                    </th>
                    <th>
                      <input
                        aria-label="Filter size"
                        value={filters.columnFilters.file_size_bytes}
                        onChange={(event) => updateColumnFilter("file_size_bytes", event.target.value)}
                        placeholder="Size"
                      />
                    </th>
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
          </div>
          <DeletePreviewDrawer
            plan={dryRunPlan}
            result={deleteResult}
            message={deleteMessage}
            busy={deleteBusy}
            open={previewOpen}
            onClose={() => setPreviewOpen(false)}
            onExecute={executeConfirmedDelete}
          />
        </main>
      )}
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  activeSortKey,
  direction,
  onSort
}: {
  label: string;
  sortKey: SortKey;
  activeSortKey: SortKey;
  direction: "asc" | "desc";
  onSort: (key: SortKey) => void;
}) {
  const isActive = activeSortKey === sortKey;
  return (
    <th aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button className={`sort-button ${isActive ? "active" : ""}`} onClick={() => onSort(sortKey)}>
        <span>{label}</span>
        {isActive ? (direction === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />) : null}
      </button>
    </th>
  );
}

function DeletePreviewDrawer({
  plan,
  result,
  message,
  busy,
  open,
  onClose,
  onExecute
}: {
  plan: DeleteDryRunPlan | null;
  result: DeleteExecuteResponse | null;
  message: string;
  busy: boolean;
  open: boolean;
  onClose: () => void;
  onExecute: (confirmation: string) => Promise<void>;
}) {
  const [confirmation, setConfirmation] = useState("");

  if (!open || !plan) return null;
  const canExecute = confirmation === "DELETE" && !busy;

  return (
    <>
      <button className="drawer-backdrop" aria-label="Close delete preview" onClick={onClose} />
      <aside className="preview-drawer" aria-label="Delete preview">
        <div className="preview-heading">
          <ShieldCheck size={19} />
          <div>
            <h2>Delete preview</h2>
            <p>No destructive action will run until confirmed.</p>
          </div>
          <button className="drawer-close" title="Close delete preview" aria-label="Close delete preview" onClick={onClose}>
            <X size={17} />
          </button>
        </div>

        <div className="dry-run">
          <div className="estimate">
            <span>Storage reclaim estimate</span>
            <strong>{formatBytes(plan.storage_reclaim_estimate_bytes)}</strong>
          </div>
          {plan.global_warnings.map((warning) => (
            <p className="warning" key={warning}>{warning}</p>
          ))}
          {plan.items.map((item) => (
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

        <section className="execute-panel" aria-label="Real delete confirmation">
          <h3>Execute deletion</h3>
          <p>
            This calls Radarr/Sonarr with delete files enabled for the selected items. Type <strong>DELETE</strong> to unlock it.
          </p>
          <label className="field">
            <span>Confirmation</span>
            <input
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              placeholder="Type DELETE"
              autoComplete="off"
            />
          </label>
          <button className="danger execute-button" disabled={!canExecute} onClick={() => onExecute(confirmation)}>
            <Trash2 size={16} />
            Execute confirmed delete
          </button>
          {message ? <p className="execute-message">{message}</p> : null}
          {result ? (
            <div className="execute-result">
              <strong>{result.deleted_count} item(s) processed</strong>
              <span>{formatBytes(result.storage_reclaim_estimate_bytes)} requested reclaim</span>
              {result.global_warnings.map((warning) => (
                <p className="warning" key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}
        </section>
      </aside>
    </>
  );
}

function DuplicatesView() {
  const [data, setData] = useState<DuplicatesListResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [plan, setPlan] = useState<DuplicatesDryRunPlan | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [message, setMessage] = useState("Loading duplicates...");
  const [typeFilter, setTypeFilter] = useState<"all" | "movie" | "show">("all");
  const [searchFilter, setSearchFilter] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const result = await getDuplicates();
        setData(result);
        setMessage(result.total === 0
          ? "No duplicates found. Run a sync to update the cache."
          : `${result.total} item(s) found with both local and NAS copies.`
        );
      } catch {
        setMessage("Failed to load duplicates. Check that the backend is reachable and a sync has run.");
      }
    }
    load();
  }, []);

  const items = useMemo(() => {
    if (!data) return [];
    return data.items.filter((item) => {
      if (typeFilter !== "all" && item.media_type !== typeFilter) return false;
      if (searchFilter && !item.title.toLowerCase().includes(searchFilter.toLowerCase())) return false;
      return true;
    });
  }, [data, typeFilter, searchFilter]);

  const allSelected = items.length > 0 && items.every((item) => selectedIds.has(item.id));

  function toggleItem(id: number) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((item) => item.id)));
    }
  }

  async function runDryRun() {
    if (selectedIds.size === 0) return;
    const ids = [...selectedIds];
    try {
      const result = await createDuplicatesDryRun(ids);
      setPlan(result);
      setPreviewOpen(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Dry-run failed.");
    }
  }

  const selectedItems = items.filter((item) => selectedIds.has(item.id));
  const reclaimableSelected = selectedItems.reduce((sum, item) => sum + item.reclaimable_bytes, 0);

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <h1>Duplicates</h1>
          <p>{message}</p>
        </div>
        {data && data.total > 0 ? (
          <div className="action-group">
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Total reclaimable: {formatBytes(data.total_reclaimable_bytes)}
            </span>
          </div>
        ) : null}
      </header>

      <section className="toolbar" aria-label="Duplicate filters and actions">
        <label className="search-box">
          <Search size={17} />
          <input
            value={searchFilter}
            onChange={(event) => setSearchFilter(event.target.value)}
            placeholder="Search title"
          />
        </label>

        <div className="segmented">
          <button className={typeFilter === "all" ? "active" : ""} onClick={() => setTypeFilter("all")}>All</button>
          <button className={typeFilter === "movie" ? "active" : ""} onClick={() => setTypeFilter("movie")}>Movies</button>
          <button className={typeFilter === "show" ? "active" : ""} onClick={() => setTypeFilter("show")}>TV Shows</button>
        </div>

        <div className="action-group">
          <button className="danger" disabled={selectedIds.size === 0} onClick={runDryRun}>
            <Trash2 size={16} />
            Dry-run remove local copy
          </button>
          {plan && !previewOpen ? (
            <button onClick={() => setPreviewOpen(true)}>
              <PanelRightOpen size={16} />
              View dry-run preview
            </button>
          ) : null}
        </div>
      </section>

      {data && items.length > 0 ? (
        <div className="content-grid">
          <section className="table-panel" aria-label="Duplicate media items">
            <div className="table-summary">
              <span>{items.length} filtered</span>
              <span>{selectedIds.size} selected</span>
              {selectedIds.size > 0 ? (
                <span>{formatBytes(reclaimableSelected)} selected reclaimable</span>
              ) : null}
            </div>
            <table>
              <thead>
                <tr>
                  <th className="select-cell">
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                  </th>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Dupe files</th>
                  <th>Local quality</th>
                  <th>NAS quality</th>
                  <th>Size to reclaim</th>
                  <th>Manager</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <DuplicateRow
                    key={item.id}
                    item={item}
                    selected={selectedIds.has(item.id)}
                    onToggle={toggleItem}
                  />
                ))}
              </tbody>
            </table>
          </section>
        </div>
      ) : null}

      {previewOpen && plan ? (
        <DuplicatesDryRunDrawer
          plan={plan}
          open={previewOpen}
          onClose={() => setPreviewOpen(false)}
        />
      ) : null}
    </main>
  );
}

function uniqueQualities(values: string[]): string {
  const seen = [...new Set(values)];
  if (seen.length === 0) return "—";
  if (seen.length === 1) return seen[0];
  return `${seen.length} qualities`;
}

function DuplicateRow({
  item,
  selected,
  onToggle
}: {
  item: DuplicateItem;
  selected: boolean;
  onToggle: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const versions = item.duplicate_versions;
  const localQuality = uniqueQualities(versions.map((v) => v.local_quality));
  const nasQuality = uniqueQualities(versions.map((v) => v.nas_quality));
  const fileLabel = item.media_type === "movie"
    ? "1 movie"
    : `${versions.length} episode${versions.length === 1 ? "" : "s"}`;

  return (
    <>
      <tr className={selected ? "selected-row" : ""}>
        <td className="select-cell">
          <input type="checkbox" checked={selected} onChange={() => onToggle(item.id)} />
        </td>
        <td>
          <button
            className="text-button"
            onClick={() => setExpanded((v) => !v)}
            title="Show per-file detail"
          >
            <strong>{item.title}</strong>
          </button>
          <span>{item.year ?? "Unknown"}</span>
        </td>
        <td>{item.media_type === "movie" ? "Movie" : "TV Show"}</td>
        <td>{fileLabel}</td>
        <td><span className="qual-badge local-path">{localQuality}</span></td>
        <td><span className="qual-badge nas-path">{nasQuality}</span></td>
        <td>{formatBytes(item.reclaimable_bytes)}</td>
        <td>{item.manager_kind}</td>
      </tr>
      {expanded ? (
        <tr className="path-detail-row">
          <td />
          <td colSpan={7}>
            <div className="dupe-detail">
              <table className="dupe-episodes">
                <thead>
                  <tr>
                    <th>Episode/File</th>
                    <th>Local quality (delete)</th>
                    <th>NAS quality (keep)</th>
                    <th>Reclaim</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.identity + v.local_path}>
                      <td>{v.identity}</td>
                      <td>
                        <span className="qual-badge local-path">{v.local_quality}</span>
                        <span className="path-hint" title={v.local_path}>{truncatePath(v.local_path, 70)}</span>
                      </td>
                      <td>
                        <span className="qual-badge nas-path">{v.nas_quality}</span>
                        <span className="path-hint" title={v.nas_path}>{truncatePath(v.nas_path, 70)}</span>
                      </td>
                      <td>{formatBytes(v.local_size_bytes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function DuplicatesDryRunDrawer({
  plan,
  open,
  onClose
}: {
  plan: DuplicatesDryRunPlan;
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <>
      <button className="drawer-backdrop" aria-label="Close dry-run preview" onClick={onClose} />
      <aside className="preview-drawer" aria-label="Duplicates dry-run preview">
        <div className="preview-heading">
          <ShieldCheck size={19} />
          <div>
            <h2>Duplicates dry-run preview</h2>
            <p>No files will be deleted — this is a preview only.</p>
          </div>
          <button className="drawer-close" title="Close" aria-label="Close" onClick={onClose}>
            <X size={17} />
          </button>
        </div>

        <div className="dry-run">
          <div className="estimate">
            <span>Storage to reclaim</span>
            <strong>{formatBytes(plan.total_reclaimable_bytes)}</strong>
          </div>
          {plan.global_warnings.map((warning) => (
            <p className="warning" key={warning}>{warning}</p>
          ))}
          {plan.items.map((item) => (
            <div className="plan-item" key={item.media_item_id}>
              <strong>{item.title}</strong>
              <span>
                {item.library} · {item.manager_kind} · {item.episode_count} file(s) · {formatBytes(item.reclaimable_bytes)}
              </span>
              {item.warnings.map((w) => (
                <p className="warning" key={w}>{w}</p>
              ))}
              <ol>
                {item.steps.map((step, idx) => (
                  <li key={`${item.media_item_id}-${idx}-${step.action}`}>
                    <b>{step.service}</b>
                    <small style={{ whiteSpace: "pre-wrap" }}>{step.detail}</small>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>

        <section className="execute-panel" aria-label="Execute note">
          <p>
            <strong>Execute not yet available.</strong> Review the steps above, then run a sync to verify the preview is still accurate before deletion is enabled.
          </p>
        </section>
      </aside>
    </>
  );
}

function truncatePath(path: string, maxLen = 60): string {
  if (path.length <= maxLen) return path;
  const filename = path.split("/").pop() ?? path;
  if (filename.length >= maxLen) return "…/" + filename.slice(-maxLen + 2);
  const prefix = path.slice(0, maxLen - filename.length - 3);
  return `${prefix}…/${filename}`;
}

function SettingsView({ onSaved }: { onSaved: () => Promise<void> }) {
  const [config, setConfig] = useState<ServiceConfigResponse | null>(null);
  const [form, setForm] = useState<ConfigForm | null>(null);
  const [validation, setValidation] = useState<ConnectionValidationResponse | null>(null);
  const [message, setMessage] = useState("Loading settings...");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const next = await getConfig();
        setConfig(next);
        setForm(toForm(next));
        setMessage(`Config file: ${next.config_path}`);
      } catch {
        setMessage("Unable to load settings from the backend.");
      }
    }
    load();
  }, []);

  function update<K extends keyof ConfigForm>(key: K, value: ConfigForm[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  }

  async function save() {
    if (!form) return;
    setBusy(true);
    setMessage("Saving settings...");
    try {
      const saved = await saveConfig(toUpdate(form));
      setConfig(saved);
      setForm(toForm(saved));
      setMessage("Settings saved.");
      await onSaved();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Settings save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    setBusy(true);
    setMessage("Running read-only connection checks...");
    try {
      const result = await validateConfig();
      setValidation(result);
      setMessage("Connection checks finished.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Connection validation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!form || !config) {
    return (
      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>Settings</h1>
            <p>{message}</p>
          </div>
        </header>
      </main>
    );
  }

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <h1>Settings</h1>
          <p>{message}</p>
        </div>
        <div className="action-group">
          <button onClick={validate} disabled={busy}>
            <CheckCircle2 size={16} />
            Test connections
          </button>
          <button onClick={save} disabled={busy}>
            <Save size={16} />
            Save settings
          </button>
        </div>
      </header>

      <section className="settings-grid">
        <ServicePanel title="Plex" secretSet={config.plex_token_set} secretPlaceholder={config.plex_token_placeholder}>
          <TextField label="Plex URL" value={form.plex_url} onChange={(value) => update("plex_url", value)} />
          <SecretField label="Plex token" value={form.plex_token} onChange={(value) => update("plex_token", value)} />
          <TextField
            label="Library names"
            value={form.plex_library_names}
            onChange={(value) => update("plex_library_names", value)}
          />
        </ServicePanel>

        <ServicePanel
          title="Tautulli"
          secretSet={config.tautulli_api_key_set}
          secretPlaceholder={config.tautulli_api_key_placeholder}
        >
          <TextField label="Tautulli URL" value={form.tautulli_url} onChange={(value) => update("tautulli_url", value)} />
          <SecretField
            label="Tautulli API key"
            value={form.tautulli_api_key}
            onChange={(value) => update("tautulli_api_key", value)}
          />
        </ServicePanel>

        <ServicePanel title="Sonarr" secretSet={config.sonarr_api_key_set} secretPlaceholder={config.sonarr_api_key_placeholder}>
          <TextField label="Sonarr URL" value={form.sonarr_url} onChange={(value) => update("sonarr_url", value)} />
          <SecretField label="Sonarr API key" value={form.sonarr_api_key} onChange={(value) => update("sonarr_api_key", value)} />
        </ServicePanel>

        <ServicePanel title="Radarr" secretSet={config.radarr_api_key_set} secretPlaceholder={config.radarr_api_key_placeholder}>
          <TextField label="Radarr URL" value={form.radarr_url} onChange={(value) => update("radarr_url", value)} />
          <SecretField label="Radarr API key" value={form.radarr_api_key} onChange={(value) => update("radarr_api_key", value)} />
        </ServicePanel>

        <ServicePanel title="Seerr" secretSet={config.seerr_api_key_set} secretPlaceholder={config.seerr_api_key_placeholder}>
          <label className="field">
            <span>Seerr type</span>
            <select
              value={form.seerr_kind}
              onChange={(event) => update("seerr_kind", event.target.value as ConfigForm["seerr_kind"])}
            >
              <option value="overseerr">Overseerr</option>
              <option value="jellyseerr">Jellyseerr</option>
            </select>
          </label>
          <TextField label="Seerr URL" value={form.seerr_url} onChange={(value) => update("seerr_url", value)} />
          <SecretField label="Seerr API key" value={form.seerr_api_key} onChange={(value) => update("seerr_api_key", value)} />
        </ServicePanel>

        <ServicePanel
          title="Legacy Overseerr"
          secretSet={config.legacy_seerr_api_key_set}
          secretPlaceholder={config.legacy_seerr_api_key_placeholder}
        >
          <TextField
            label="Legacy Overseerr URL"
            value={form.legacy_seerr_url}
            onChange={(value) => update("legacy_seerr_url", value)}
          />
          <SecretField
            label="Legacy Overseerr API key"
            value={form.legacy_seerr_api_key}
            onChange={(value) => update("legacy_seerr_api_key", value)}
          />
        </ServicePanel>

        <section className="settings-panel">
          <div className="settings-panel-heading">
            <div>
              <h2>Sync</h2>
              <span>Runtime</span>
            </div>
          </div>
          <label className="field">
            <span>Sync interval minutes</span>
            <input
              type="number"
              min={5}
              max={1440}
              value={form.sync_interval_minutes}
              onChange={(event) => update("sync_interval_minutes", Number(event.target.value))}
            />
          </label>
        </section>
      </section>

      {validation ? (
        <section className="validation-panel">
          <h2>Connection checks</h2>
          <div className="validation-list">
            {validation.integrations.map((item) => (
              <div className="validation-row" key={item.name}>
                <span className={`status-dot ${item.state}`} />
                <strong>{item.name}</strong>
                <small>{item.state}</small>
                <p>{item.detail}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function ServicePanel({
  title,
  secretSet,
  secretPlaceholder,
  children
}: {
  title: string;
  secretSet: boolean;
  secretPlaceholder: boolean;
  children: ReactNode;
}) {
  return (
    <section className="settings-panel">
      <div className="settings-panel-heading">
        <div>
          <h2>{title}</h2>
          <span>{secretSet && !secretPlaceholder ? "Key stored" : "Key needed"}</span>
        </div>
        <KeyRound size={18} />
      </div>
      {children}
    </section>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SecretField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Stored value kept when blank"
      />
    </label>
  );
}

function toForm(config: ServiceConfigResponse): ConfigForm {
  return {
    plex_url: config.plex_url,
    plex_token: "",
    plex_library_names: config.plex_library_names.join(", "),
    tautulli_url: config.tautulli_url,
    tautulli_api_key: "",
    sonarr_url: config.sonarr_url,
    sonarr_api_key: "",
    radarr_url: config.radarr_url,
    radarr_api_key: "",
    seerr_kind: config.seerr_kind,
    seerr_url: config.seerr_url,
    seerr_api_key: "",
    legacy_seerr_url: config.legacy_seerr_url,
    legacy_seerr_api_key: "",
    sync_interval_minutes: config.sync_interval_minutes
  };
}

function toUpdate(form: ConfigForm): ServiceConfigUpdate {
  return {
    plex_url: form.plex_url,
    plex_token: form.plex_token || null,
    plex_library_names: form.plex_library_names.split(",").map((item) => item.trim()).filter(Boolean),
    tautulli_url: form.tautulli_url,
    tautulli_api_key: form.tautulli_api_key || null,
    sonarr_url: form.sonarr_url,
    sonarr_api_key: form.sonarr_api_key || null,
    radarr_url: form.radarr_url,
    radarr_api_key: form.radarr_api_key || null,
    seerr_kind: form.seerr_kind,
    seerr_url: form.seerr_url,
    seerr_api_key: form.seerr_api_key || null,
    legacy_seerr_url: form.legacy_seerr_url,
    legacy_seerr_api_key: form.legacy_seerr_api_key || null,
    sync_interval_minutes: form.sync_interval_minutes
  };
}
