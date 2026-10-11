import { ItemView, WorkspaceLeaf } from "obsidian";

export const CONCEPT_MAP_VIEW_TYPE = "fvsc-concept-map";
interface MapNode { term: string; evidence_count: number; source_ids: string[]; source_count: number }
interface MapData {
  focus: string | null; snapshot_id: string; nodes: MapNode[];
  edges: { source: string; target: string; relation: string; polarity: number; modality: number; count: number; source_ids: string[] }[];
  total_neighbors: number;
}

export class ConceptMapView extends ItemView {
  private focusTerm: string | undefined;
  private requestNumber = 0;
  private backStack: (string | undefined)[] = [];

  constructor(leaf: WorkspaceLeaf, private baseUrl: () => string) { super(leaf); }
  getViewType(): string { return CONCEPT_MAP_VIEW_TYPE; }
  getDisplayText(): string { return "Карта понятий FVSC"; }
  getIcon(): string { return "git-fork"; }
  async onOpen(): Promise<void> {
    const term = this.getState().focus;
    await this.focus(typeof term === "string" ? term : undefined, false);
  }
  getState(): Record<string, unknown> { return { focus: this.focusTerm }; }
  async setState(state: Record<string, unknown>, result: { history: boolean }): Promise<void> {
    await super.setState(state, result);
    await this.focus(typeof state.focus === "string" ? state.focus : undefined, false);
  }
  async focus(term?: string, remember = true): Promise<void> {
    const request = ++this.requestNumber;
    try {
      const response = await fetch(`${this.baseUrl()}/v1/map${term ? `?focus=${encodeURIComponent(term)}` : ""}`);
      if (!response.ok) throw new Error(`Карта недоступна (HTTP ${response.status}). Синхронизируй записи.`);
      const data = await response.json() as MapData;
      if (request !== this.requestNumber) return;
      if (remember && this.focusTerm !== term) this.backStack.push(this.focusTerm);
      this.focusTerm = data.focus ?? undefined;
      this.render(data);
    } catch (error) {
      if (request !== this.requestNumber) return;
      this.contentEl.empty();
      this.contentEl.createEl("p", { text: String(error), cls: "fvsc-error" });
      this.contentEl.createEl("button", { text: "Повторить" }).onclick = () => void this.focus(term, false);
    }
  }
  private render(data: MapData): void {
    this.contentEl.empty();
    this.contentEl.addClass("fvsc-concept-map");
    const bar = this.contentEl.createDiv({ cls: "fvsc-toolbar" });
    const back = bar.createEl("button", { text: "Назад" });
    back.disabled = this.backStack.length === 0;
    back.onclick = () => void this.focus(this.backStack.pop(), false);
    bar.createEl("button", { text: "Обновить" }).onclick = () => void this.focus(this.focusTerm, false);
    this.contentEl.createEl("h3", { text: data.focus ?? "Карта пока пуста" });
    this.contentEl.createEl("p", { text: "Нажми на понятие, чтобы открыть его связи. Линии показывают извлечённые связи, которые могут требовать проверки." });
    if (!data.focus) return;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 900 620");
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", `Связи понятия ${data.focus}`);
    svg.classList.add("fvsc-map-svg");
    this.contentEl.appendChild(svg);
    const positions = new Map<string, [number, number]>();
    positions.set(data.focus, [450, 300]);
    const others = data.nodes.filter(n => n.term !== data.focus);
    others.forEach((node, index) => {
      const a = 2 * Math.PI * index / Math.max(1, others.length) - Math.PI / 2;
      positions.set(node.term, [450 + 365 * Math.cos(a), 300 + 265 * Math.sin(a)]);
    });
    for (const edge of data.edges) {
      const from = positions.get(edge.source), to = positions.get(edge.target);
      if (!from || !to) continue;
      const line = document.createElementNS(ns, "line");
      for (const [key, value] of Object.entries({ x1: from[0], y1: from[1], x2: to[0], y2: to[1] })) line.setAttribute(key, String(value));
      line.classList.add("fvsc-map-edge");
      const title = document.createElementNS(ns, "title");
      title.textContent = `${edge.source} → ${edge.polarity < 0 ? "НЕ " : ""}${edge.relation} → ${edge.target} (модальность ${edge.modality})`;
      line.appendChild(title); svg.appendChild(line);
    }
    for (const node of data.nodes) {
      const [x, y] = positions.get(node.term)!;
      const group = document.createElementNS(ns, "g");
      group.setAttribute("transform", `translate(${x},${y})`);
      group.setAttribute("role", "button"); group.setAttribute("tabindex", "0");
      group.setAttribute("aria-label", `Открыть понятие ${node.term}`);
      group.classList.add("fvsc-map-node");
      if (node.term === data.focus) group.classList.add("is-focused");
      const box = document.createElementNS(ns, "rect");
      const width = node.term === data.focus ? 180 : 136;
      for (const [key, value] of Object.entries({ x: -width / 2, y: -18, width, height: 36, rx: 12 })) box.setAttribute(key, String(value));
      const label = document.createElementNS(ns, "text");
      label.setAttribute("text-anchor", "middle"); label.setAttribute("dy", "5");
      label.textContent = node.term.length > 17 ? node.term.slice(0, 16) + "…" : node.term;
      const title = document.createElementNS(ns, "title"); title.textContent = node.term;
      group.append(box, label, title);
      group.addEventListener("click", () => void this.focus(node.term));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); void this.focus(node.term); }
      });
      svg.appendChild(group);
    }
    this.contentEl.createEl("p", { text: `Показано соседей: ${others.length} из ${data.total_neighbors}` });
    const current = data.nodes.find(n => n.term === data.focus)!;
    const sources = this.contentEl.createEl("details");
    sources.createEl("summary", { text: `Исходные записи: ${current.source_count}` });
    for (const source of current.source_ids) {
      sources.createEl("button", { text: source }).onclick = () => void this.app.workspace.openLinkText(source, "", true);
    }
    const edges = this.contentEl.createEl("details");
    edges.createEl("summary", { text: "Какие связи показаны" });
    for (const edge of data.edges) {
      const row = edges.createEl("p", { text: `${edge.source} → ${edge.polarity < 0 ? "НЕ " : ""}${edge.relation} → ${edge.target} (модальность ${edge.modality}) ` });
      for (const source of edge.source_ids.slice(0, 3)) row.createEl("button", { text: source }).onclick = () => void this.app.workspace.openLinkText(source, "", true);
    }
  }
  async onClose(): Promise<void> { ++this.requestNumber; }
}
