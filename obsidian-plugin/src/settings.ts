import { App, PluginSettingTab, Setting, Notice } from "obsidian";
import type FvscPlugin from "./main";
import { detectPython, detectRepo, getPluginAbsDir } from "./paths";

export interface FvscSettings {
  pythonPath: string;
  fvscRepoPath: string;
  port: number;
  modelName: string;
  autoStart: boolean;
}

export const DEFAULT_SETTINGS: FvscSettings = {
  pythonPath: "",
  fvscRepoPath: "",
  port: 8765,
  modelName: "qwen2.5:14b-instruct-q4_K_M",
  autoStart: true,
};

export class FvscSettingTab extends PluginSettingTab {
  plugin: FvscPlugin;

  constructor(app: App, plugin: FvscPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "FVSC Antourage" });
    containerEl.createEl("p", {
      text:
        "Плагин запускает локальный движок карты и LLM-чат. Все поля плагин старается " +
        "найти автоматически — заполняй вручную только если ниже написано «Не найдено».",
      cls: "setting-item-description",
    });

    new Setting(containerEl)
      .setName("Путь к Python")
      .setDesc("Полный путь к python.exe или python. Найдётся автоматически, если Python установлен правильно.")
      .addText((text) =>
        text
          .setPlaceholder("…/python.exe")
          .setValue(this.plugin.settings.pythonPath)
          .onChange(async (v) => {
            this.plugin.settings.pythonPath = v.trim();
            await this.plugin.saveSettings();
          }),
      );
    const pyHintEl = containerEl.createDiv({ cls: "fvsc-autodetect-hint" });
    void this.renderAutodetectHint(pyHintEl, "python");

    new Setting(containerEl)
      .setName("Папка FVSC")
      .setDesc("Папка с распакованным FVSC. Найдётся автоматически, если FVSC лежит рядом с плагином или в стандартном месте.")
      .addText((text) =>
        text
          .setPlaceholder("…/FVSC")
          .setValue(this.plugin.settings.fvscRepoPath)
          .onChange(async (v) => {
            this.plugin.settings.fvscRepoPath = v.trim();
            await this.plugin.saveSettings();
          }),
      );
    const repoHintEl = containerEl.createDiv({ cls: "fvsc-autodetect-hint" });
    void this.renderAutodetectHint(repoHintEl, "repo");

    new Setting(containerEl)
      .setName("Порт")
      .setDesc("По умолчанию 8765. Менять только если 8765 занят.")
      .addText((text) =>
        text
          .setValue(String(this.plugin.settings.port))
          .onChange(async (v) => {
            const n = parseInt(v, 10);
            if (Number.isFinite(n) && n > 0 && n < 65536) {
              this.plugin.settings.port = n;
              await this.plugin.saveSettings();
            }
          }),
      );

    new Setting(containerEl)
      .setName("Модель LLM")
      .setDesc("Имя модели Ollama для чата с картой.")
      .addText((text) =>
        text
          .setValue(this.plugin.settings.modelName)
          .onChange(async (v) => {
            this.plugin.settings.modelName = v.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Запускать движок при старте Obsidian")
      .setDesc("Если выключено — запускать вручную через команду «Open Antourage».")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.autoStart).onChange(async (v) => {
          this.plugin.settings.autoStart = v;
          await this.plugin.saveSettings();
        }),
      );

    new Setting(containerEl)
      .setName("Перезапустить движок")
      .setDesc("Применить изменения без перезагрузки Obsidian.")
      .addButton((b) =>
        b
          .setButtonText("Перезапустить")
          .setCta()
          .onClick(async () => {
            try {
              await this.plugin.backend.restart();
              new Notice("FVSC: движок карты перезапущен.");
            } catch (e) {
              new Notice(`FVSC: не удалось перезапустить — ${String(e)}`);
            }
          }),
      );
  }

  /**
   * Show "Found automatically: PATH [Use]" under a path field when it's empty
   * and detection succeeded; show "Not found — fill in manually" otherwise.
   */
  private async renderAutodetectHint(el: HTMLElement, kind: "python" | "repo"): Promise<void> {
    el.empty();
    const s = this.plugin.settings;
    const current = kind === "python" ? s.pythonPath : s.fvscRepoPath;
    if (current) return;

    const pluginAbsDir = getPluginAbsDir(this.app, this.plugin.manifest.dir);
    if (!pluginAbsDir) {
      el.createSpan({ text: "Не удалось определить папку плагина — укажи путь вручную." });
      return;
    }

    el.createSpan({ text: "Ищу автоматически…" });

    let found: string | null = null;
    if (kind === "repo") {
      found = await detectRepo(pluginAbsDir);
    } else {
      const repoForPython = s.fvscRepoPath || (await detectRepo(pluginAbsDir));
      found = await detectPython(pluginAbsDir, repoForPython);
    }

    el.empty();
    if (found) {
      el.createSpan({ text: `Найдено: ${found} ` });
      const btn = el.createEl("button", { text: "Использовать" });
      btn.onclick = async () => {
        if (kind === "python") s.pythonPath = found!;
        else s.fvscRepoPath = found!;
        await this.plugin.saveSettings();
        this.display();
      };
    } else {
      el.createSpan({ text: "Не найдено автоматически — укажи путь вручную." });
    }
  }
}
