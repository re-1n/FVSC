import { Modal, Notice } from "obsidian";
import type FvscPlugin from "./main";
import type { BackendController } from "./backend";

interface RuntimeStatus {
  loaded: boolean;
  source_count: number;
  ledger_events: number;
  active_events: number;
  exact_judgments: number;
}

/** First-run local vault synchronization over the clean FVSC service. */
export class BootstrapModal extends Modal {
  private static activeInstance: BootstrapModal | null = null;

  private abortController: AbortController | null = null;
  private watcherWasPaused = false;

  constructor(
    private plugin: FvscPlugin,
    private backend: BackendController,
    private onDone: () => void,
  ) {
    super(plugin.app);
  }

  static async maybeShow(
    plugin: FvscPlugin,
    backend: BackendController,
    onDone: () => void,
  ): Promise<void> {
    if (BootstrapModal.activeInstance) return;
    try {
      const response = await fetch(`${backend.baseUrl()}/v1/status`);
      if (!response.ok) return;
      const status = await response.json() as RuntimeStatus;
      if (status.loaded) return;
      new BootstrapModal(plugin, backend, onDone).open();
    } catch {
      // Backend warm-up is retried by the plugin; do not show a false error.
    }
  }

  onOpen(): void {
    BootstrapModal.activeInstance = this;
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Синхронизировать vault с FVSC" });
    contentEl.createEl("p", {
      text:
        "FVSC прочитает Markdown локально, сохранит append-only evidence cache " +
        "и построит поисковый индекс в памяти. Сырые тексты не копируются в cache.",
    });
    const row = contentEl.createDiv({ cls: "fvsc-modal-buttons" });
    const build = row.createEl("button", { text: "Синхронизировать", cls: "mod-cta" });
    const cancel = row.createEl("button", { text: "Отмена" });
    cancel.onclick = () => this.close();
    build.onclick = () => {
      build.disabled = true;
      cancel.disabled = true;
      void this.startSync();
    };
  }

  private async startSync(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Синхронизирую…" });
    const stage = contentEl.createDiv({ cls: "fvsc-progress-stage" });
    stage.setText("Сканирую источники и сверяю ревизии.");
    const progress = contentEl.createDiv({ cls: "fvsc-progress-wrap" });
    const bar = progress.createDiv({ cls: "fvsc-progress-bar fvsc-progress-indeterminate" });
    bar.style.width = "35%";
    const cancel = contentEl.createEl("button", { text: "Отмена" });

    if (this.plugin.watcher) {
      this.plugin.watcher.pause();
      this.watcherWasPaused = true;
    }
    this.abortController = new AbortController();
    cancel.onclick = () => this.abortController?.abort();

    try {
      const response = await fetch(`${this.backend.baseUrl()}/v1/vault/sync`, {
        method: "POST",
        signal: this.abortController.signal,
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        stage.setText(`Ошибка синхронизации: HTTP ${response.status} ${detail}`);
        bar.style.width = "0%";
        return;
      }
      const status = await response.json() as RuntimeStatus;
      bar.classList.remove("fvsc-progress-indeterminate");
      bar.style.width = "100%";
      stage.setText(
        `Готово: ${status.source_count} источников, ` +
        `${status.exact_judgments} проверяемых relations.`,
      );
      new Notice(`FVSC: синхронизировано ${status.source_count} источников`);
      window.setTimeout(() => {
        this.close();
        this.onDone();
      }, 600);
    } catch (error) {
      if ((error as { name?: string }).name !== "AbortError") {
        stage.setText(`Ошибка сети: ${String(error)}`);
      }
    } finally {
      if (this.watcherWasPaused && this.plugin.watcher) {
        this.plugin.watcher.resume();
        this.watcherWasPaused = false;
      }
    }
  }

  onClose(): void {
    this.abortController?.abort();
    if (this.watcherWasPaused && this.plugin.watcher) {
      this.plugin.watcher.resume();
      this.watcherWasPaused = false;
    }
    this.contentEl.empty();
    if (BootstrapModal.activeInstance === this) {
      BootstrapModal.activeInstance = null;
    }
  }
}
