import { Plugin, WorkspaceLeaf, Notice, TFile, normalizePath } from "obsidian";
import { DEFAULT_SETTINGS, FvscSettings, FvscSettingTab } from "./settings";
import { BackendController, BackendStatus } from "./backend";
import { AntourageView, ANTOURAGE_VIEW_TYPE } from "./view";
import { VaultWatcher } from "./vault_watcher";
import { BootstrapModal } from "./bootstrap";
import { autoFillSettings } from "./paths";
import { tryAutoStartOllama } from "./ollama";
import { VoiceController } from "./voice";

export default class FvscPlugin extends Plugin {
  settings!: FvscSettings;
  backend!: BackendController;
  // Exposed for BootstrapModal to pause/resume during initial map build.
  watcher: VaultWatcher | null = null;
  private statusEl: HTMLElement | null = null;
  private syncIndicator = "";
  private voiceIndicator = "";
  private voice: VoiceController | null = null;

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
    this.voice = new VoiceController({
      app: this.app,
      baseUrl: () => this.backend.baseUrl(),
      ensureBackend: () => this.ensureBackendUp(),
      onRecordingState: (recording, detail) => {
        this.voiceIndicator = recording ? `voice recording${detail ? `: ${detail}` : ""}` : "";
        this.renderStatus(this.backend.getStatus());
      },
    });
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

    this.addCommand({
      id: "rebuild-pilot-ledger",
      name: "Pilot: rebuild semantic ledger",
      callback: async () => this.rebuildPilotLedger(),
    });

    this.addCommand({
      id: "open-pilot-daily-review",
      name: "Pilot: create daily semantic review",
      callback: async () => this.createPilotDailyReview(),
    });

    this.addCommand({
      id: "voice-import-audio",
      name: "Voice: import audio file",
      callback: async () => this.voice?.importAudio(),
    });

    this.addCommand({
      id: "voice-toggle-memo",
      name: "Voice: start/stop owner voice memo",
      callback: async () => this.voice?.toggleVoiceMemo(),
    });

    this.addCommand({
      id: "voice-open-review",
      name: "Voice: open transcript review queue",
      callback: () => this.voice?.openReviewQueue(),
    });

    this.addCommand({
      id: "voice-emergency-stop",
      name: "Voice: emergency stop",
      callback: async () => this.voice?.emergencyStop(),
    });

    this.addRibbonIcon("git-fork", "Open Antourage", () => this.openAntourageView());
    this.addRibbonIcon("mic", "Start/stop FVSC voice memo", () => void this.voice?.toggleVoiceMemo());

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
        void this.startOllamaIfAvailable();
        void this.backend.start().then(() => {
          if (this.backend.getStatus() === "up") {
            // Backend reports "up" the moment uvicorn's port opens, but
            // /viz/status may still 500 for a beat while the router warms.
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
        const r = await fetch(`${this.backend.baseUrl()}/viz/status`);
        if (r.ok) {
          void BootstrapModal.maybeShow(this, this.backend, () => this.reloadOpenAntourageViews());
          return;
        }
      } catch { /* keep retrying */ }
    }
  }

  private async ensureBackendUp(): Promise<boolean> {
    if (this.backend.getStatus() !== "up") {
      await this.backend.start();
    }
    if (this.backend.getStatus() !== "up") {
      new Notice("FVSC Pilot: backend is not available.");
      return false;
    }
    return true;
  }

  private async rebuildPilotLedger(): Promise<void> {
    if (!(await this.ensureBackendUp())) return;
    new Notice("FVSC Pilot: rebuilding evidence ledger…");
    try {
      const response = await fetch(`${this.backend.baseUrl()}/pilot/rebuild`, { method: "POST" });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = await response.json();
      const errors = Array.isArray(data.errors) ? data.errors.length : 0;
      new Notice(
        `FVSC Pilot: indexed ${data.files_indexed}/${data.files_seen} notes, ` +
        `${data.concept_count} concepts${errors ? `, errors: ${errors}` : ""}.`,
        8000,
      );
    } catch (error) {
      console.error("[fvsc-pilot] rebuild failed", error);
      new Notice(`FVSC Pilot: rebuild failed — ${String(error)}`, 10000);
    }
  }

  private async createPilotDailyReview(): Promise<void> {
    if (!(await this.ensureBackendUp())) return;
    try {
      let status = await fetch(`${this.backend.baseUrl()}/pilot/status`);
      if (!status.ok) throw new Error(await status.text());
      let statusData = await status.json();
      if (!statusData.state_exists || statusData.active_event_count === 0) {
        await this.rebuildPilotLedger();
        status = await fetch(`${this.backend.baseUrl()}/pilot/status`);
        if (!status.ok) throw new Error(await status.text());
        statusData = await status.json();
      }

      const response = await fetch(`${this.backend.baseUrl()}/pilot/daily-review?limit=10`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      const markdown = this.renderPilotDailyReview(data);
      const folder = normalizePath("_fvsc_review");
      const path = normalizePath(`${folder}/FVSC Daily Review.md`);
      if (!this.app.vault.getAbstractFileByPath(folder)) {
        await this.app.vault.createFolder(folder);
      }
      const existing = this.app.vault.getAbstractFileByPath(path);
      let file: TFile;
      if (existing instanceof TFile) {
        await this.app.vault.modify(existing, markdown);
        file = existing;
      } else {
        file = await this.app.vault.create(path, markdown);
      }
      await this.app.workspace.getLeaf("tab").openFile(file);
      new Notice("FVSC Pilot: daily review created.");
    } catch (error) {
      console.error("[fvsc-pilot] daily review failed", error);
      new Notice(`FVSC Pilot: daily review failed — ${String(error)}`, 10000);
    }
  }

  private renderPilotDailyReview(data: {
    snapshot_id?: string;
    concepts?: Array<{
      term: string;
      mass: number;
      evidence_count: number;
      polysemy_entropy: number;
      sources: string[];
      related: Array<{ term: string; score: number }>;
    }>;
    recent_sources?: Array<{ path: string; active_assertions: number }>;
  }): string {
    const lines: string[] = [
      "# FVSC Pilot — Daily Review",
      "",
      `Generated: ${new Date().toISOString()}`,
      `Snapshot: \`${String(data.snapshot_id ?? "unknown").slice(0, 16)}\``,
      "",
      "> Экспериментальный обзор. Связи являются гипотезами модели, а не утверждениями о вас.",
      "",
    ];
    for (const concept of data.concepts ?? []) {
      lines.push(`## ${concept.term}`);
      lines.push(`- Evidence: ${concept.evidence_count}; mass: ${concept.mass.toFixed(3)}; entropy: ${concept.polysemy_entropy.toFixed(3)}`);
      if (concept.sources?.length) {
        lines.push(`- Sources: ${concept.sources.map((source) => `[[${source.replace(/\.md$/i, "")}]]`).join(", ")}`);
      }
      if (concept.related?.length) {
        lines.push(`- Related: ${concept.related.map((item) => `${item.term} (${item.score.toFixed(3)})`).join(", ")}`);
      }
      lines.push("- [ ] Полезно / точно");
      lines.push("- [ ] Неточно / случайно");
      lines.push("");
    }
    if (data.recent_sources?.length) {
      lines.push("## Recently active sources", "");
      for (const source of data.recent_sources) {
        lines.push(`- [[${source.path.replace(/\.md$/i, "")}]] — ${source.active_assertions} assertions`);
      }
      lines.push("");
    }
    lines.push("## Notes", "", "- ");
    return lines.join("\n");
  }

  async onunload() {
    await this.voice?.dispose();
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
    const indicators = [this.syncIndicator, this.voiceIndicator].filter(Boolean);
    const suffix = indicators.length ? `  ${indicators.join(" · ")}` : "";
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
