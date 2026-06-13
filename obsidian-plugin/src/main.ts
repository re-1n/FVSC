import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { DEFAULT_SETTINGS, FvscSettings, FvscSettingTab } from "./settings";
import { BackendController, BackendStatus } from "./backend";
import { AntourageView, ANTOURAGE_VIEW_TYPE } from "./view";
import { VaultWatcher } from "./vault_watcher";
import { BootstrapModal } from "./bootstrap";
import { autoFillSettings } from "./paths";

export default class FvscPlugin extends Plugin {
  settings!: FvscSettings;
  backend!: BackendController;
  // Exposed for BootstrapModal to pause/resume during initial map build.
  watcher: VaultWatcher | null = null;
  private statusEl: HTMLElement | null = null;
  private syncIndicator = "";

  async onload() {
    await this.loadSettings();

    // Try to find Python and FVSC repo automatically before anything else —
    // mass-adoption guardrail: a fresh install should not require manual paths.
    await autoFillSettings(this);

    const vaultPath = (this.app.vault.adapter as { getBasePath?: () => string }).getBasePath?.() ?? "";

    this.backend = new BackendController(
      () => this.settings,
      {
        vaultPath,
        onStatus: (s, d) => this.renderStatus(s, d),
        onConfigError: () => this.openOwnSettings(),
      },
    );

    this.statusEl = this.addStatusBarItem();
    this.renderStatus("stopped");

    this.registerView(
      ANTOURAGE_VIEW_TYPE,
      (leaf: WorkspaceLeaf) =>
        new AntourageView(
          leaf,
          () => this.backend.baseUrl(),
          () => this,
          () => this.backend,
        ),
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
        new Notice("FVSC: движок карты перезапущен.");
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
    this.watcher.start((evt) => this.registerEvent(evt as Parameters<typeof this.registerEvent>[0]));

    if (this.settings.autoStart) {
      if (!this.settings.pythonPath || !this.settings.fvscRepoPath) {
        new Notice("FVSC: не удалось найти Python или папку FVSC автоматически. Открой Настройки → FVSC Antourage.");
        window.setTimeout(() => this.openOwnSettings(), 500);
      } else {
        void this.backend.start().then(() => {
          if (this.backend.getStatus() === "up") {
            // Give /viz/status a moment to be fully responsive, then check
            // whether the user needs a first-time build.
            window.setTimeout(() => {
              void BootstrapModal.maybeShow(this, this.backend, () => this.reloadOpenAntourageViews());
            }, 1000);
          }
        });
      }
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

  reloadOpenAntourageViews(): void {
    for (const leaf of this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE)) {
      const v = leaf.view;
      if (v instanceof AntourageView) v.reload();
    }
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  /** Open this plugin's own tab in the Settings dialog. Uses a semi-private
   *  API that's been stable across Obsidian's lifetime; fallback is a Notice. */
  openOwnSettings(): void {
    const setting = (this.app as unknown as {
      setting?: { open?: () => void; openTabById?: (id: string) => void };
    }).setting;
    if (setting?.open && setting?.openTabById) {
      setting.open();
      setting.openTabById(this.manifest.id);
    } else {
      new Notice("Открой Настройки → Community plugins → FVSC Antourage.");
    }
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
