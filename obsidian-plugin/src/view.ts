import { ItemView, WorkspaceLeaf, App } from "obsidian";
import type FvscPlugin from "./main";
import type { BackendController } from "./backend";
import { BootstrapModal } from "./bootstrap";

export const ANTOURAGE_VIEW_TYPE = "fvsc-antourage-view";

interface VizStatus {
  vault_cache_exists: boolean;
  space_loaded: boolean;
  bootstrap_running: boolean;
  ollama_up: boolean;
  concept_count?: number | null;
}

export class AntourageView extends ItemView {
  private getBaseUrl: () => string;
  private getPlugin: () => FvscPlugin;
  private getBackend: () => BackendController;
  private iframe: HTMLIFrameElement | null = null;

  constructor(
    leaf: WorkspaceLeaf,
    getBaseUrl: () => string,
    getPlugin: () => FvscPlugin,
    getBackend: () => BackendController,
  ) {
    super(leaf);
    this.getBaseUrl = getBaseUrl;
    this.getPlugin = getPlugin;
    this.getBackend = getBackend;
  }

  getViewType(): string {
    return ANTOURAGE_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Antourage";
  }

  getIcon(): string {
    return "git-fork";
  }

  async onOpen(): Promise<void> {
    // Detach every other AntourageView leaf — collapse all duplicates onto
    // the freshest instance (this one). Symmetric: whichever view onOpen
    // fires last wins, the rest disappear. Avoids the prior bug where two
    // copies of the view rendered side-by-side inside the same pane.
    for (const peer of this.app.workspace.getLeavesOfType(ANTOURAGE_VIEW_TYPE)) {
      if (peer.view !== this) peer.detach();
    }

    this.contentEl.empty();
    this.contentEl.addClass("fvsc-antourage-view");

    const toolbar = this.contentEl.createDiv({ cls: "fvsc-toolbar" });
    const reloadBtn = toolbar.createEl("button", { cls: "fvsc-toolbar-btn", text: "Перезагрузить карту" });
    reloadBtn.onclick = () => this.reload();
    const obsidianGraphBtn = toolbar.createEl("button", { cls: "fvsc-toolbar-btn", text: "Открыть Obsidian-граф" });
    obsidianGraphBtn.onclick = () => this.openObsidianGraphSplit();

    let status: VizStatus | null = null;
    try {
      const r = await fetch(`${this.getBaseUrl()}/viz/status`);
      if (r.ok) status = await r.json();
    } catch {
      /* backend not up */
    }

    if (!status) {
      const cta = this.contentEl.createDiv({ cls: "fvsc-empty-cta" });
      cta.createEl("p", { text: "Движок карты не отвечает." });
      cta.createEl("p", { text: "Проверь статус-бар внизу или открой Настройки → FVSC Antourage." });
      return;
    }

    // CTA only when there's truly no data — neither in memory nor on disk.
    // vault_cache_exists alone is enough: /viz/status now lazy-loads from disk,
    // and the iframe's /viz call will trigger load if status didn't manage to.
    if (!status.space_loaded && !status.vault_cache_exists) {
      const cta = this.contentEl.createDiv({ cls: "fvsc-empty-cta" });
      cta.createEl("p", { text: "Карта этого vault'а ещё не построена." });
      const btn = cta.createEl("button", { text: "Построить карту", cls: "mod-cta" });
      btn.onclick = () => {
        btn.disabled = true;
        btn.setText("Открываю…");
        void BootstrapModal.maybeShow(this.getPlugin(), this.getBackend(), () => this.reload())
          .finally(() => {
            btn.disabled = false;
            btn.setText("Построить карту");
          });
      };
      return;
    }

    // Cache exists but space not yet hydrated — show a tiny loading line.
    // The iframe will trigger /viz which performs the load (~0.5–1s for big caches).
    if (!status.space_loaded && status.vault_cache_exists) {
      const loading = this.contentEl.createDiv({ cls: "fvsc-empty-cta" });
      loading.createEl("p", { text: "Загружаю карту из cache…" });
    }

    if (!status.ollama_up) {
      const hint = this.contentEl.createDiv({ cls: "fvsc-ollama-hint" });
      hint.createSpan({ text: "Чат не подключён. Запусти Ollama чтобы говорить с картой. " });
      const link = hint.createEl("a", { text: "Установить Ollama", href: "https://ollama.com/download" });
      link.setAttr("target", "_blank");
      link.setAttr("rel", "noopener");
    }

    const frame = this.contentEl.createEl("iframe", { cls: "fvsc-antourage-frame" });
    frame.src = `${this.getBaseUrl()}/viz?top_n=100`;
    frame.setAttribute("allow", "clipboard-write");
    this.iframe = frame;
  }

  reload(): void {
    // Rerun the full onOpen so empty/ollama states are re-evaluated against
    // fresh /viz/status — not just the iframe src swap.
    void this.onOpen();
  }

  /**
   * Split this pane and open Obsidian's native graph view to the right —
   * gives the user a side-by-side comparison they can collapse anytime.
   */
  private async openObsidianGraphSplit(): Promise<void> {
    const app = this.app as App;
    const existing = app.workspace.getLeavesOfType("graph");
    if (existing.length > 0) {
      app.workspace.revealLeaf(existing[0]);
      return;
    }
    const newLeaf = app.workspace.getLeaf("split", "vertical");
    await newLeaf.setViewState({ type: "graph", active: true });
    app.workspace.revealLeaf(newLeaf);
  }

  async onClose(): Promise<void> {
    this.contentEl.empty();
    this.iframe = null;
  }
}
