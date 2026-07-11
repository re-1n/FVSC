import { App, TAbstractFile, TFile } from "obsidian";
import type { BackendController } from "./backend";

/**
 * Watches the vault for .md changes and pushes them to the FVSC backend so
 * the semantic map stays in sync without manual rebuilds.
 *
 * Per-path debouncing: rapid edits to one note collapse into a single POST.
 * The legacy visualization map and the append-only pilot ledger are updated
 * independently so a pilot failure never blocks the established map workflow.
 */

const DEBOUNCE_MS = 1500;
const MAX_FILE_SIZE = 5 * 1024 * 1024;   // 5 MB safety cap
const EXCLUDE_PREFIXES = [
  "_fvsc_concepts/",
  "_fvsc_review/",
  ".obsidian/",
  ".trash/",
  ".fvsc/",
];

export interface WatcherCallbacks {
  onActivity: (msg: string) => void;
  onIdle: () => void;
}

interface PendingChange {
  path: string;
  action: "create" | "modify" | "delete" | "rename";
  oldPath?: string;
  timer: number;
}

export class VaultWatcher {
  private app: App;
  private backend: BackendController;
  private cb: WatcherCallbacks;
  private pending: Map<string, PendingChange> = new Map();
  private active = false;
  private paused = false;

  constructor(app: App, backend: BackendController, cb: WatcherCallbacks) {
    this.app = app;
    this.backend = backend;
    this.cb = cb;
  }

  start(register: <T>(evt: T) => void): void {
    if (this.active) return;
    this.active = true;
    const v = this.app.vault;

    register(v.on("modify", (f) => this.schedule(f, "modify")));
    register(v.on("create", (f) => this.schedule(f, "create")));
    register(v.on("delete", (f) => this.schedule(f, "delete")));
    register(v.on("rename", (f, oldPath) => this.schedule(f, "rename", oldPath)));
  }

  stop(): void {
    this.active = false;
    for (const p of this.pending.values()) {
      window.clearTimeout(p.timer);
    }
    this.pending.clear();
  }

  /**
   * Temporarily drop incoming change events without unregistering vault hooks.
   * Use during bootstrap so the backend's own write-back into the vault
   * (concept notes, html map, cache) doesn't bounce through file_ingest.
   */
  pause(): void {
    this.paused = true;
    for (const p of this.pending.values()) {
      window.clearTimeout(p.timer);
    }
    this.pending.clear();
    console.log("[fvsc-watch] paused");
  }

  resume(): void {
    this.paused = false;
    console.log("[fvsc-watch] resumed");
  }

  /**
   * Flush any pending changes immediately — used on plugin unload so the
   * backend gets a chance to persist final edits before shutdown.
   */
  async flush(): Promise<void> {
    const paths = Array.from(this.pending.keys());
    for (const p of paths) {
      const pending = this.pending.get(p);
      if (!pending) continue;
      window.clearTimeout(pending.timer);
      await this.send(pending);
    }
    this.pending.clear();
  }

  private schedule(
    f: TAbstractFile,
    action: PendingChange["action"],
    oldPath?: string,
  ): void {
    if (!this.active || this.paused) return;
    if (!(f instanceof TFile)) return;
    if (f.extension !== "md") return;
    if (EXCLUDE_PREFIXES.some((p) => f.path.startsWith(p))) return;
    if (f.stat?.size && f.stat.size > MAX_FILE_SIZE) return;

    const key = f.path;
    const existing = this.pending.get(key);
    if (existing) {
      window.clearTimeout(existing.timer);
    }
    const change: PendingChange = {
      path: f.path,
      action,
      oldPath,
      timer: window.setTimeout(() => this.send({ ...change, timer: 0 }), DEBOUNCE_MS) as unknown as number,
    };
    this.pending.set(key, change);
  }

  private async send(change: PendingChange): Promise<void> {
    this.pending.delete(change.path);
    this.cb.onActivity(change.action === "delete" ? `–${shortPath(change.path)}` : `↻${shortPath(change.path)}`);

    let text: string | undefined;
    let observedAt = Date.now() / 1000;
    if (change.action !== "delete") {
      const file = this.app.vault.getAbstractFileByPath(change.path);
      if (file instanceof TFile) {
        try {
          text = await this.app.vault.cachedRead(file);
          observedAt = file.stat.mtime / 1000;
        } catch {
          /* file gone between schedule and send */
          return;
        }
      }
    }

    const payload = {
      path: change.path,
      action: change.action,
      text,
      old_path: change.oldPath,
      observed_at: observedAt,
    };

    try {
      const r = await fetch(`${this.backend.baseUrl()}/viz/file_ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        console.warn(`[fvsc-watch] ${change.action} ${change.path} → ${r.status}: ${body}`);
      } else {
        const data = await r.json();
        console.log(`[fvsc-watch] ${change.action} ${shortPath(change.path)} +${data.added}/-${data.purged}` +
          (data.saved ? " 💾" : ""));
      }

      const pilot = await fetch(`${this.backend.baseUrl()}/pilot/file_ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!pilot.ok) {
        const body = await pilot.text().catch(() => "");
        console.warn(`[fvsc-pilot] ${change.action} ${change.path} → ${pilot.status}: ${body}`);
      } else {
        const data = await pilot.json();
        console.log(`[fvsc-pilot] snapshot=${String(data.snapshot_id).slice(0, 12)} concepts=${data.concept_count}`);
      }
    } catch (err) {
      console.warn(`[fvsc-watch] network error for ${change.path}:`, err);
    } finally {
      if (this.pending.size === 0) this.cb.onIdle();
    }
  }
}

function shortPath(p: string): string {
  const segs = p.split("/");
  if (segs.length <= 2) return p;
  return `…/${segs[segs.length - 2]}/${segs[segs.length - 1]}`;
}
