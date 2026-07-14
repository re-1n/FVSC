import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { DEFAULT_SETTINGS, FvscSettings, FvscSettingTab } from "./settings";
import { BackendController, BackendStatus } from "./backend";
import { AntourageView, ANTOURAGE_VIEW_TYPE } from "./view";
import { VaultWatcher } from "./vault_watcher";
import { BootstrapModal } from "./bootstrap";
import { autoFillSettings } from "./paths";
import { tryAutoStartOllama } from "./ollama";

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

    // Session restore can leave duplicate AntourageView leaves from the
    // previous run; collapse them so the user starts with a single pane.
    this.app.workspace.onLayoutReady(() => {
      const leaves = this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE);
      for (let i = 1; i < leaves.length; i++) leaves[i].detach();
    });

    if (this.settings.autoStart) {
      if (!this.settings.pythonPath || !this.settings.fvscRepoPath) {
        new Notice("FVSC: не удалось найти Python или папку FVSC автоматически. Открой Настройки → FVSC Antourage.");
        window.setTimeout(() => this.openOwnSettings(), 500);
      } else {
        // Ollama is independent of the backend — warm both in parallel so the
        // chat is ready by the time the user opens the Antourage view.
        // Without this, mass-adoption-blocker: a fresh install with Ollama
        // present-but-not-running shows "Чат не подключён" forever and the
        // user has no idea what to do.
        void this.startOllamaIfAvailable();
        void this.backend.start().then(() => {
          if (this.backend.getStatus() === "up") {
            // Retry the first-sync check while the local runtime loads cache.
            void this.scheduleBootstrapCheck();
          }
        });
      }
    }
  }

  private async startOllamaIfAvailable(): Promise<void> {
    try {
      const r = await tryAutoStartOllama({
        modelsDir: this.settings.ollamaModelsPath || undefined,
      });
      if (r.status === "started") {
        console.log(`[fvsc-ollama] started: ${r.execPath} (models=${this.settings.ollamaModelsPath || "default"})`);
      } else if (r.status === "already_up") {
        console.log("[fvsc-ollama] already running");
      } else if (r.status === "no_binary") {
        console.log("[fvsc-ollama] binary not found — install hint will surface in view");
      } else if (r.status === "spawn_failed") {
        console.warn(`[fvsc-ollama] spawn failed: ${r.execPath}`);
      }
    } catch (e) {
      console.warn("[fvsc-ollama] orchestration error:", e);
    }
  }

  private async scheduleBootstrapCheck(): Promise<void> {
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => window.setTimeout(r, 1000));
      try {
        const r = await fetch(`${this.backend.baseUrl()}/health`);
        if (r.ok) {
          void BootstrapModal.maybeShow(this, this.backend, () => this.reloadOpenAntourageViews());
          return;
        }
      } catch { /* keep retrying */ }
    }
  }

  async onunload() {
    if (this.watcher) {
      try { await this.watcher.flush(); } catch { /* ignore */ }
      this.watcher.stop();
    }
    // Every reconciliation is atomically persisted by the clean service.
    await this.backend?.stop();
    this.app.workspace.detachLeavesOfType(ANTOURAGE_VIEW_TYPE);
  }

  async openAntourageView(): Promise<void> {
    const existing = this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE);
    if (existing.length > 0) {
      // Workspace can hold duplicates after plugin reload / session restore.
      // Keep the first, detach the rest — otherwise the user sees multiple
      // identical CTA panes on screen.
      for (let i = 1; i < existing.length; i++) {
        existing[i].detach();
      }
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
