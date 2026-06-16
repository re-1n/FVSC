import { ItemView, WorkspaceLeaf, App, Notice } from "obsidian";
import type FvscPlugin from "./main";
import type { BackendController } from "./backend";
import { BootstrapModal } from "./bootstrap";
import { detectOllama, detectOllamaModelsDir, restartOllamaWithModelsDir } from "./ollama";

export const ANTOURAGE_VIEW_TYPE = "fvsc-antourage-view";

interface VizStatus {
  vault_cache_exists: boolean;
  space_loaded: boolean;
  bootstrap_running: boolean;
  ollama_up: boolean;
  concept_count?: number | null;
  model?: string;
  models_available?: string[];
}

const OLLAMA_POLL_MS = 2_000;
// Wait until /viz/status reports !ollama_up three consecutive times before
// telling the user "Чат не подключён". One stray flap shouldn't fire the
// hint (the daemon takes a beat to bind, Obsidian's PATH is flaky, etc).
const OLLAMA_DOWN_THRESHOLD = 3;
const DEFAULT_MODEL = "qwen2.5:14b-instruct-q4_K_M";

/**
 * Curated list of Ollama models that work well as map-chat backends.
 * Names match exactly what `ollama pull` accepts. Sizes are approximate
 * disk footprint so the user can pick what fits their drive.
 */
const RECOMMENDED_MODELS: { name: string; size: string; note: string }[] = [
  { name: "qwen2.5:7b-instruct-q4_K_M",  size: "~4.7 GB", note: "лёгкая, быстрая" },
  { name: "qwen2.5:14b-instruct-q4_K_M", size: "~9 GB",   note: "рекомендую — баланс" },
  { name: "qwen2.5:32b-instruct-q4_K_M", size: "~20 GB",  note: "максимум, нужна 32GB+ RAM" },
  { name: "llama3.1:8b-instruct-q4_K_M", size: "~4.9 GB", note: "Meta, английский" },
  { name: "gemma2:9b-instruct-q4_K_M",   size: "~5.4 GB", note: "Google" },
  { name: "qwen2.5-coder:14b-instruct-q4_K_M", size: "~9 GB", note: "под код" },
];

export class AntourageView extends ItemView {
  private getBaseUrl: () => string;
  private getPlugin: () => FvscPlugin;
  private getBackend: () => BackendController;
  private iframe: HTMLIFrameElement | null = null;
  private ollamaSection: HTMLElement | null = null;
  private ollamaPollTimer: number | null = null;
  private ollamaDownStreak = 0;
  private pullAbort: AbortController | null = null;

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
    this.stopOllamaPoll();
    this.ollamaDownStreak = 0;

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

    // Reserved slot for ollama hint / model picker. Filled in by pollOllama
    // so we don't show "Чат не подключён" during the first 1-2 seconds while
    // `ollama serve` is still binding to 11434.
    this.ollamaSection = this.contentEl.createDiv({ cls: "fvsc-ollama-section" });
    this.renderOllamaSection(status);

    const frame = this.contentEl.createEl("iframe", { cls: "fvsc-antourage-frame" });
    frame.src = `${this.getBaseUrl()}/viz?top_n=100`;
    frame.setAttribute("allow", "clipboard-write");
    this.iframe = frame;

    this.startOllamaPoll();
  }

  private startOllamaPoll(): void {
    if (this.ollamaPollTimer !== null) return;
    this.ollamaPollTimer = window.setInterval(async () => {
      try {
        const r = await fetch(`${this.getBaseUrl()}/viz/status`);
        if (!r.ok) return;
        const s: VizStatus = await r.json();
        this.renderOllamaSection(s);
      } catch { /* keep polling */ }
    }, OLLAMA_POLL_MS);
  }

  private stopOllamaPoll(): void {
    if (this.ollamaPollTimer !== null) {
      window.clearInterval(this.ollamaPollTimer);
      this.ollamaPollTimer = null;
    }
  }

  /**
   * Decision tree:
   *   - !ollama_up   → install/start hint (after OLLAMA_DOWN_THRESHOLD misses).
   *   - ollama_up, available=[], settings.ollamaModelsPath set
   *                  → mismatch warning + restart-with-env button.
   *   - ollama_up, model ∈ available
   *                  → empty (chat is good to go).
   *   - ollama_up, model ∉ available
   *                  → picker with installed + recommended + custom name field.
   */
  private renderOllamaSection(status: VizStatus): void {
    if (!this.ollamaSection) return;
    const settings = this.getPlugin().settings;
    const modelName = (settings.modelName || "").trim();
    const available = status.models_available || [];

    if (!status.ollama_up) {
      this.ollamaDownStreak += 1;
      if (this.ollamaDownStreak < OLLAMA_DOWN_THRESHOLD) {
        // Could still be a warm-up flap; don't render anything yet.
        return;
      }
      this.renderOllamaDownHint();
      return;
    }

    // Up — reset streak so a future down counts from zero.
    this.ollamaDownStreak = 0;

    // Mismatch: user pointed us at a models dir but the running daemon
    // doesn't see anything → it's pre-existing tray-app launched without
    // OLLAMA_MODELS. Offer to restart it with our env.
    if (available.length === 0 && settings.ollamaModelsPath) {
      this.renderMismatchWarning(settings.ollamaModelsPath);
      return;
    }

    if (modelName && available.includes(modelName)) {
      this.ollamaSection.empty();
      return;
    }
    this.renderModelPicker(available, modelName);
  }

  private renderMismatchWarning(modelsPath: string): void {
    if (!this.ollamaSection) return;
    this.ollamaSection.empty();
    const wrap = this.ollamaSection.createDiv({ cls: "fvsc-ollama-picker" });
    wrap.createEl("p", {
      text: `Ollama запущена, но не видит моделей в ${modelsPath}. ` +
            `Скорее всего она стартовала без OLLAMA_MODELS. ` +
            `Могу её перезапустить с правильной настройкой.`,
    });
    const btn = wrap.createEl("button", { text: "Перезапустить Ollama", cls: "mod-cta" });
    btn.onclick = async () => {
      btn.disabled = true;
      btn.setText("Перезапускаю…");
      try {
        const exec = await detectOllama();
        if (!exec) {
          new Notice("FVSC: ollama не найден.");
          btn.disabled = false;
          btn.setText("Перезапустить Ollama");
          return;
        }
        const r = await restartOllamaWithModelsDir(exec, modelsPath);
        if (r.ok) {
          new Notice("FVSC: Ollama перезапущена с твоей папкой моделей.");
        } else {
          new Notice("FVSC: не удалось дождаться Ollama после перезапуска.");
        }
      } catch (e) {
        new Notice(`FVSC: ошибка перезапуска — ${String(e)}`);
      } finally {
        btn.disabled = false;
        btn.setText("Перезапустить Ollama");
      }
    };
  }

  private renderOllamaDownHint(): void {
    if (!this.ollamaSection) return;
    this.ollamaSection.empty();
    const hint = this.ollamaSection.createDiv({ cls: "fvsc-ollama-hint" });
    hint.createSpan({ text: "Чат не подключён. Запусти Ollama чтобы говорить с картой. " });
    const link = hint.createEl("a", { text: "Установить Ollama", href: "https://ollama.com/download" });
    link.setAttr("target", "_blank");
    link.setAttr("rel", "noopener");
  }

  private renderModelPicker(available: string[], configured: string): void {
    if (!this.ollamaSection) return;
    this.ollamaSection.empty();
    const wrap = this.ollamaSection.createDiv({ cls: "fvsc-ollama-picker" });

    // Headline depends on whether the user already has something pulled.
    if (available.length === 0) {
      wrap.createEl("p", {
        text: "Ollama запущена, но моделей не скачано. Выбери одну из рекомендованных:",
      });
    } else if (configured) {
      wrap.createEl("p", {
        text: `Модель ${configured} не найдена. Выбери одну из установленных или скачай новую:`,
      });
    } else {
      wrap.createEl("p", { text: "Выбери модель для чата:" });
    }

    // ── Installed (radio-pick, no download needed) ─────────────────
    if (available.length > 0) {
      wrap.createEl("h4", { text: "Установлено у тебя:", cls: "fvsc-ollama-h" });
      const list = wrap.createDiv({ cls: "fvsc-ollama-models" });
      for (const m of available) {
        const row = list.createEl("label", { cls: "fvsc-ollama-model-row" });
        const radio = row.createEl("input");
        radio.type = "radio";
        radio.name = "fvsc-model";
        row.createSpan({ text: ` ${m}` });
        radio.onclick = () => this.selectModel(m);
      }
    }

    // ── Recommended (not yet installed → pull button) ───────────────
    const toRecommend = RECOMMENDED_MODELS.filter((m) => !available.includes(m.name));
    if (toRecommend.length > 0) {
      wrap.createEl("h4", { text: "Рекомендованные:", cls: "fvsc-ollama-h" });
      const recList = wrap.createDiv({ cls: "fvsc-ollama-models" });
      for (const m of toRecommend) {
        const row = recList.createDiv({ cls: "fvsc-ollama-rec-row" });
        const meta = row.createDiv({ cls: "fvsc-ollama-rec-meta" });
        meta.createEl("strong", { text: m.name });
        meta.createSpan({ text: ` · ${m.size} · ${m.note}`, cls: "fvsc-ollama-rec-note" });
        const dlBtn = row.createEl("button", { text: "Скачать" });
        dlBtn.onclick = () => this.beginPull(m.name);
      }
    }

    // ── Custom: any name from ollama.com/library ────────────────────
    wrap.createEl("h4", { text: "Своя модель:", cls: "fvsc-ollama-h" });
    const customRow = wrap.createDiv({ cls: "fvsc-ollama-custom" });
    const input = customRow.createEl("input", { cls: "fvsc-ollama-custom-input" });
    input.type = "text";
    input.placeholder = "например llama3.2:3b-instruct-q4_K_M";
    const pullBtn = customRow.createEl("button", { text: "Скачать" });
    pullBtn.onclick = () => {
      const name = input.value.trim();
      if (!name) {
        new Notice("Введи имя модели из ollama.com/library");
        return;
      }
      this.beginPull(name);
    };
  }

  private async selectModel(model: string): Promise<void> {
    const plugin = this.getPlugin();
    plugin.settings.modelName = model;
    await plugin.saveSettings();
    new Notice(`FVSC: модель ${model} выбрана. Перезапускаю движок…`);
    try {
      await this.getBackend().restart();
      new Notice("FVSC: движок перезапущен.");
    } catch (e) {
      new Notice(`FVSC: не удалось перезапустить — ${String(e)}`);
    }
    // Refresh the section so it disappears (model now matches available).
    try {
      const r = await fetch(`${this.getBaseUrl()}/viz/status`);
      if (r.ok) this.renderOllamaSection(await r.json());
    } catch { /* ignore */ }
  }

  /**
   * Stream POST /viz/ollama_pull and render percent. On success, set the
   * model in settings and reload the section so the picker disappears.
   */
  private async beginPull(model: string): Promise<void> {
    if (!this.ollamaSection) return;
    this.pullAbort?.abort();
    this.pullAbort = new AbortController();

    this.ollamaSection.empty();
    const wrap = this.ollamaSection.createDiv({ cls: "fvsc-ollama-picker" });
    wrap.createEl("p", { text: `Скачиваю ${model}…` });
    const stage = wrap.createDiv({ cls: "fvsc-progress-stage" });
    stage.setText("Подключаюсь…");
    const barWrap = wrap.createDiv({ cls: "fvsc-progress-wrap" });
    const bar = barWrap.createDiv({ cls: "fvsc-progress-bar" });
    bar.style.width = "0%";
    const cancelBtn = wrap.createEl("button", { text: "Отмена" });
    cancelBtn.onclick = () => this.pullAbort?.abort();

    try {
      const resp = await fetch(`${this.getBaseUrl()}/viz/ollama_pull`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ model }),
        signal: this.pullAbort.signal,
      });
      if (!resp.ok || !resp.body) {
        stage.setText(`Ошибка: HTTP ${resp.status}`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          if (!this.handlePullFrame(frame, bar, stage, model)) return;
        }
      }
    } catch (e) {
      if ((e as { name?: string }).name === "AbortError") {
        stage.setText("Отменено.");
        return;
      }
      stage.setText(`Ошибка сети: ${String(e)}`);
    }
  }

  /** Returns false on terminal frame (done/error) so the caller stops reading. */
  private handlePullFrame(
    frame: string,
    bar: HTMLElement,
    stage: HTMLElement,
    model: string,
  ): boolean {
    let eventType = "message";
    let dataStr = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
    }
    let data: { percent?: number | null; status?: string; message?: string } = {};
    try { data = JSON.parse(dataStr); } catch { /* malformed */ }

    if (eventType === "progress") {
      const pct = typeof data.percent === "number" ? data.percent : null;
      if (pct !== null) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
      if (data.status) stage.setText(data.status);
      return true;
    }
    if (eventType === "done") {
      bar.style.width = "100%";
      stage.setText("Готово.");
      void this.afterPullSuccess(model);
      return false;
    }
    if (eventType === "error") {
      stage.setText(`Ошибка: ${data.message || "неизвестная"}`);
      return false;
    }
    return true;
  }

  private async afterPullSuccess(model: string): Promise<void> {
    const plugin = this.getPlugin();
    plugin.settings.modelName = model;
    await plugin.saveSettings();
    new Notice(`FVSC: ${model} скачана. Перезапускаю движок…`);
    try {
      await this.getBackend().restart();
      new Notice("FVSC: движок перезапущен.");
    } catch (e) {
      new Notice(`FVSC: не удалось перезапустить — ${String(e)}`);
    }
    try {
      const r = await fetch(`${this.getBaseUrl()}/viz/status`);
      if (r.ok) this.renderOllamaSection(await r.json());
    } catch { /* ignore */ }
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
    this.stopOllamaPoll();
    this.pullAbort?.abort();
    this.pullAbort = null;
    this.contentEl.empty();
    this.iframe = null;
    this.ollamaSection = null;
  }
}
