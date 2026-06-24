import {
  Archive,
  CheckCircle2,
  Database,
  Download,
  KeyRound,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Tags,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { createDeleteDryRun, getConfig, getMedia, getStatus, runSync, saveConfig, validateConfig } from "./api";
import { buildMockDryRun, mockMedia, mockStatus } from "./lib/mockData";
import { filterMedia, toCsv } from "./lib/filters";
import { formatBytes, formatDate } from "./lib/format";
import type {
  ConnectionValidationResponse,
  DeleteDryRunPlan,
  FilterState,
  LibraryName,
  MediaItem,
  ServiceConfigResponse,
  ServiceConfigUpdate,
  StatusResponse
} from "./types";

const LIBRARIES: LibraryName[] = ["Movies", "TV Shows"];

type View = "media" | "settings";

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
  sync_interval_minutes: number;
}

export function App() {
  const [activeLibrary, setActiveLibrary] = useState<LibraryName>("Movies");
  const [activeView, setActiveView] = useState<View>("media");
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
  const [syncMessage, setSyncMessage] = useState("");

  async function loadMedia(library = activeLibrary) {
    try {
      const [nextStatus, media] = await Promise.all([getStatus(), getMedia(library)]);
      setStatus(nextStatus);
      setItems(media.items);
      setApiNote(nextStatus.demo_mode ? "Demo mode from backend" : "Connected to backend cache");
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

        <nav className="library-tabs" aria-label="Navigation">
          {LIBRARIES.map((library) => (
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
      )}
    </div>
  );
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
    sync_interval_minutes: form.sync_interval_minutes
  };
}
