import { App, PluginSettingTab, Setting, Notice } from "obsidian";
import type FvscPlugin from "./main";

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
      text: "Plugin controls the local FastAPI backend that powers the semantic map and LLM chat. Backend is a Python process — paths below are required.",
      cls: "setting-item-description",
    });

    new Setting(containerEl)
      .setName("Python interpreter")
      .setDesc("Absolute path to python.exe inside the FVSC venv. Example: C:\\Users\\you\\Desktop\\FVSC\\venv\\Scripts\\python.exe")
      .addText((text) =>
        text
          .setPlaceholder("…/venv/Scripts/python.exe")
          .setValue(this.plugin.settings.pythonPath)
          .onChange(async (v) => {
            this.plugin.settings.pythonPath = v.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("FVSC repo path")
      .setDesc("Absolute path to the FVSC project root (used as cwd for uvicorn).")
      .addText((text) =>
        text
          .setPlaceholder("…/FVSC")
          .setValue(this.plugin.settings.fvscRepoPath)
          .onChange(async (v) => {
            this.plugin.settings.fvscRepoPath = v.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Port")
      .setDesc("Local port for uvicorn. Change only if 8765 is taken.")
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
      .setName("LLM model")
      .setDesc("Ollama model tag. Passed to the backend via FVSC_LLM_MODEL env var.")
      .addText((text) =>
        text
          .setValue(this.plugin.settings.modelName)
          .onChange(async (v) => {
            this.plugin.settings.modelName = v.trim();
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Auto-start backend")
      .setDesc("Spawn the FastAPI process when the plugin loads.")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.autoStart).onChange(async (v) => {
          this.plugin.settings.autoStart = v;
          await this.plugin.saveSettings();
        }),
      );

    new Setting(containerEl)
      .setName("Restart backend")
      .setDesc("Apply settings without reloading Obsidian.")
      .addButton((b) =>
        b
          .setButtonText("Restart")
          .setCta()
          .onClick(async () => {
            try {
              await this.plugin.backend.restart();
              new Notice("FVSC backend restarted.");
            } catch (e) {
              new Notice(`FVSC restart failed: ${String(e)}`);
            }
          }),
      );
  }
}
