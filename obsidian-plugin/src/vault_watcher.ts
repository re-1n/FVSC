import { App, TAbstractFile } from "obsidian";
import type { BackendController } from "./backend";

/** Coalesce vault changes into one canonical full-source reconciliation. */

const DEBOUNCE_MS = 1_500;
const EXCLUDE_PREFIXES = ["_fvsc_concepts/", ".fvsc/", ".obsidian/", ".trash/"];

export interface WatcherCallbacks {
  onActivity: (message: string) => void;
  onIdle: () => void;
}

export class VaultWatcher {
  private timer: number | null = null;
  private active = false;
  private paused = false;
  private dirtyPaths = new Set<string>();
  private syncing = false;

  constructor(
    private app: App,
    private backend: BackendController,
    private callbacks: WatcherCallbacks,
  ) {}

  start(register: <T>(event: T) => void): void {
    if (this.active) return;
    this.active = true;
    const vault = this.app.vault;
    register(vault.on("modify", (file) => this.schedule(file)));
    register(vault.on("create", (file) => this.schedule(file)));
    register(vault.on("delete", (file) => this.schedule(file)));
    register(vault.on("rename", (file, oldPath) => {
      this.dirtyPaths.add(oldPath);
      this.schedule(file);
    }));
  }

  stop(): void {
    this.active = false;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.dirtyPaths.clear();
  }

  pause(): void {
    this.paused = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.dirtyPaths.clear();
  }

  resume(): void {
    this.paused = false;
  }

  async flush(): Promise<void> {
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    if (this.dirtyPaths.size > 0) await this.synchronize();
  }

  private schedule(file: TAbstractFile): void {
    if (!this.active || this.paused) return;
    const path = file.path;
    if (!path.toLowerCase().endsWith(".md")) return;
    if (EXCLUDE_PREFIXES.some((prefix) => path.startsWith(prefix))) return;
    this.dirtyPaths.add(path);
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => {
      this.timer = null;
      void this.synchronize();
    }, DEBOUNCE_MS);
  }

  private async synchronize(): Promise<void> {
    if (this.syncing || this.paused || this.dirtyPaths.size === 0) return;
    this.syncing = true;
    const changed = this.dirtyPaths.size;
    this.dirtyPaths.clear();
    this.callbacks.onActivity(`↻${changed}`);
    try {
      const response = await fetch(`${this.backend.baseUrl()}/v1/vault/sync`, {
        method: "POST",
      });
      if (!response.ok) {
        console.warn(`[fvsc-watch] sync failed: HTTP ${response.status}`);
      } else {
        const status = await response.json() as { source_count: number; ledger_events: number };
        console.log(
          `[fvsc-watch] reconciled ${status.source_count} sources, ` +
          `${status.ledger_events} ledger events`,
        );
      }
    } catch (error) {
      console.warn("[fvsc-watch] sync request failed:", error);
    } finally {
      this.syncing = false;
      this.callbacks.onIdle();
      // Changes may have arrived while the reconciliation was running.
      if (this.dirtyPaths.size > 0 && !this.paused) {
        this.timer = window.setTimeout(() => {
          this.timer = null;
          void this.synchronize();
        }, DEBOUNCE_MS);
      }
    }
  }
}
