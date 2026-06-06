import { ItemView, WorkspaceLeaf, App } from "obsidian";

export const ANTOURAGE_VIEW_TYPE = "fvsc-antourage-view";

export class AntourageView extends ItemView {
  private getBaseUrl: () => string;
  private iframe: HTMLIFrameElement | null = null;

  constructor(leaf: WorkspaceLeaf, getBaseUrl: () => string) {
    super(leaf);
    this.getBaseUrl = getBaseUrl;
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
    this.contentEl.empty();
    this.contentEl.addClass("fvsc-antourage-view");

    const toolbar = this.contentEl.createDiv({ cls: "fvsc-toolbar" });

    const reloadBtn = toolbar.createEl("button", { cls: "fvsc-toolbar-btn", text: "Перезагрузить карту" });
    reloadBtn.onclick = () => this.reload();

    const obsidianGraphBtn = toolbar.createEl("button", { cls: "fvsc-toolbar-btn", text: "Открыть Obsidian-граф" });
    obsidianGraphBtn.onclick = () => this.openObsidianGraphSplit();

    const frame = this.contentEl.createEl("iframe", { cls: "fvsc-antourage-frame" });
    frame.src = `${this.getBaseUrl()}/viz?top_n=100`;
    frame.setAttribute("allow", "clipboard-write");
    this.iframe = frame;
  }

  reload(): void {
    if (this.iframe) {
      this.iframe.src = `${this.getBaseUrl()}/viz?top_n=100`;
    }
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
