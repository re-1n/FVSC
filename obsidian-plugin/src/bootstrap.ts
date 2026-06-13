import { Modal, Notice } from "obsidian";
import type FvscPlugin from "./main";
import type { BackendController } from "./backend";

interface VizStatus {
  vault_cache_exists: boolean;
  space_loaded: boolean;
  bootstrap_running: boolean;
}

/**
 * Modal that walks the user through the first-time map build:
 *   - Confirm step: "no map yet, build it?" → [Build] [Cancel]
 *   - Progress step: progress bar + stage text, driven by SSE from
 *     POST /viz/build_from_vault.
 * On success, fires the onDone callback so the host (plugin) can refresh the view.
 */
export class BootstrapModal extends Modal {
  private plugin: FvscPlugin;
  private backend: BackendController;
  private onDone: () => void;
  private abortController: AbortController | null = null;
  private watcherWasPaused = false;

  constructor(plugin: FvscPlugin, backend: BackendController, onDone: () => void) {
    super(plugin.app);
    this.plugin = plugin;
    this.backend = backend;
    this.onDone = onDone;
  }

  /**
   * Open the modal only if there's actually no map yet.
   * No-op when a build is already running or a cache exists.
   */
  static async maybeShow(
    plugin: FvscPlugin,
    backend: BackendController,
    onDone: () => void,
  ): Promise<void> {
    try {
      const r = await fetch(`${backend.baseUrl()}/viz/status`);
      if (!r.ok) return;
      const s: VizStatus = await r.json();
      if (s.bootstrap_running) return;
      if (s.vault_cache_exists || s.space_loaded) return;
      new BootstrapModal(plugin, backend, onDone).open();
    } catch {
      /* backend not up yet — silent */
    }
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Построить карту vault'а" });
    contentEl.createEl("p", {
      text:
        "У тебя ещё нет карты этого vault'а. Я могу её построить — займёт около 2 минут на ~700 файлов. " +
        "Карта строится локально, ничего не уходит в сеть.",
    });

    const btnRow = contentEl.createDiv({ cls: "fvsc-modal-buttons" });
    const buildBtn = btnRow.createEl("button", { text: "Построить", cls: "mod-cta" });
    const cancelBtn = btnRow.createEl("button", { text: "Отмена" });

    cancelBtn.onclick = () => this.close();
    buildBtn.onclick = () => void this.startBuild();
  }

  private async startBuild(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Строю карту…" });

    const stageText = contentEl.createDiv({ cls: "fvsc-progress-stage" });
    stageText.setText("Подключаюсь…");

    const barWrap = contentEl.createDiv({ cls: "fvsc-progress-wrap" });
    const bar = barWrap.createDiv({ cls: "fvsc-progress-bar" });
    bar.style.width = "0%";

    const btnRow = contentEl.createDiv({ cls: "fvsc-modal-buttons" });
    const cancelBtn = btnRow.createEl("button", { text: "Отмена" });
    cancelBtn.onclick = () => {
      this.abortController?.abort();
      this.close();
    };

    // Pause the vault watcher so it doesn't bounce on the backend's own
    // write-backs to <vault>/_fvsc_concepts/ etc. EXCLUDE_PREFIXES already
    // covers _fvsc_concepts/, but a temporary pause is cheap insurance.
    if (this.plugin.watcher) {
      this.watcherWasPaused = true;
      this.plugin.watcher.pause();
    }

    this.abortController = new AbortController();

    try {
      const resp = await fetch(`${this.backend.baseUrl()}/viz/build_from_vault`, {
        method: "POST",
        headers: { Accept: "text/event-stream" },
        signal: this.abortController.signal,
      });
      if (!resp.ok || !resp.body) {
        stageText.setText(`Ошибка: HTTP ${resp.status}`);
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
          if (!this.handleSSEFrame(frame, bar, stageText)) {
            // done or error — stop reading
            return;
          }
        }
      }
    } catch (e) {
      if ((e as { name?: string }).name === "AbortError") return;
      stageText.setText(`Ошибка сети: ${String(e)}`);
    } finally {
      if (this.watcherWasPaused && this.plugin.watcher) {
        this.plugin.watcher.resume();
        this.watcherWasPaused = false;
      }
    }
  }

  /** Returns false when a terminal event (done/error) was processed. */
  private handleSSEFrame(
    frame: string,
    bar: HTMLElement,
    stageText: HTMLElement,
  ): boolean {
    let eventType = "message";
    let dataStr = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
    }
    let data: { percent?: number; message?: string; concept_count?: number; time_total?: number } = {};
    try {
      data = JSON.parse(dataStr);
    } catch {
      /* ignore malformed frame */
    }

    if (eventType === "progress") {
      const pct = Math.max(0, Math.min(100, data.percent ?? 0));
      bar.style.width = `${pct}%`;
      if (data.message) stageText.setText(data.message);
      return true;
    }
    if (eventType === "done") {
      bar.style.width = "100%";
      const n = data.concept_count ?? 0;
      const t = Math.round(data.time_total ?? 0);
      stageText.setText(`Готово. ${n} концептов за ${t}с.`);
      new Notice(`FVSC: карта построена (${n} концептов)`);
      window.setTimeout(() => {
        this.close();
        this.onDone();
      }, 800);
      return false;
    }
    if (eventType === "error") {
      stageText.setText(`Ошибка: ${data.message || "неизвестная"}`);
      return false;
    }
    return true;
  }

  onClose(): void {
    this.abortController?.abort();
    if (this.watcherWasPaused && this.plugin.watcher) {
      this.plugin.watcher.resume();
      this.watcherWasPaused = false;
    }
    this.contentEl.empty();
  }
}
