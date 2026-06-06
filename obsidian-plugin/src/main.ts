import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { DEFAULT_SETTINGS, FvscSettings, FvscSettingTab } from "./settings";
import { BackendController, BackendStatus } from "./backend";
import { AntourageView, ANTOURAGE_VIEW_TYPE } from "./view";
import { VaultWatcher } from "./vault_watcher";

export default class FvscPlugin extends Plugin {
  settings!: FvscSettings;
  backend!: BackendController;
  private statusEl: HTMLElement | null = null;
  private watcher: VaultWatcher | null = null;
  private syncIndicator = "";   // "" | activity msg

  async onload() {
    await this.loadSettings();

    const vaultPath = (this.app.vault.adapter as any).getBasePath?.() ?? "";

    this.backend = new BackendController(
      () => this.settings,
      {
        vaultPath,
        onStatus: (s, d) => this.renderStatus(s, d),
      },
    );

    this.statusEl = this.addStatusBarItem();
    this.renderStatus("stopped");

    this.registerView(
      ANTOURAGE_VIEW_TYPE,
      (leaf: WorkspaceLeaf) => new AntourageView(leaf, () => this.backend.baseUrl()),
    );

    this.addCommand({
      id: "open-antourage",
      name: "Open Antourage",
      callback: () => this.openAntourageView(),
    });

    this.addCommand({
      id: "restart-backend",
      name: "Restart backend",
      callback: async () => {
        await this.backend.restart();
        new Notice("FVSC backend restarted.");
      },
    });

    this.addRibbonIcon("git-fork", "Open Antourage", () => this.openAntourageView());

    this.addSettingTab(new FvscSettingTab(this.app, this));

    // Live vault watcher — starts only after backend is up so we don't queue
    // hundreds of file events into a dead socket.
    this.watcher = new VaultWatcher(this.app, this.backend, {
      onActivity: (msg) => { this.syncIndicator = msg; this.renderStatus(this.backend.getStatus()); },
      onIdle: () => { this.syncIndicator = ""; this.renderStatus(this.backend.getStatus()); },
    });
    this.watcher.start((evt) => this.registerEvent(evt as any));

    if (this.settings.autoStart) {
      void this.backend.start();
    }
  }

  async onunload() {
    if (this.watcher) {
      try { await this.watcher.flush(); } catch { /* ignore */ }
      this.watcher.stop();
    }
    if (this.backend?.getStatus() === "up") {
      // Best-effort: ask backend to persist any unsaved live ingests.
      try { await fetch(`${this.backend.baseUrl()}/viz/save_cache`, { method: "POST" }); } catch { /* ignore */ }
    }
    await this.backend?.stop();
    this.app.workspace.detachLeavesOfType(ANTOURAGE_VIEW_TYPE);
  }

  async openAntourageView(): Promise<void> {
    const existing = this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE);
    if (existing.length > 0) {
      this.app.workspace.revealLeaf(existing[0]);
      const view = existing[0].view;
      if (view instanceof AntourageView) view.reload();
      return;
    }
    const leaf = this.app.workspace.getLeaf("tab");
    await leaf.setViewState({ type: ANTOURAGE_VIEW_TYPE, active: true });
    this.app.workspace.revealLeaf(leaf);
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  private renderStatus(s: BackendStatus, detail?: string) {
    if (!this.statusEl) return;
    const color: Record<BackendStatus, string> = {
      stopped: "var(--text-faint)",
      starting: "var(--color-orange)",
      up: "var(--color-green)",
      failed: "var(--color-red)",
    };
    const label: Record<BackendStatus, string> = {
      stopped: "FVSC: off",
      starting: "FVSC: starting",
      up: "FVSC: up",
      failed: "FVSC: failed",
    };
    this.statusEl.empty();
    const dot = this.statusEl.createSpan({ cls: "fvsc-status-dot" });
    dot.style.color = color[s];
    dot.setText("●");
    const suffix = this.syncIndicator ? `  ${this.syncIndicator}` : "";
    this.statusEl.createSpan({ text: ` ${label[s]}${suffix}` });
    if (detail) {
      this.statusEl.setAttribute("aria-label", detail);
      this.statusEl.title = detail;
    } else {
      this.statusEl.removeAttribute("aria-label");
      this.statusEl.title = "";
    }
  }
}
