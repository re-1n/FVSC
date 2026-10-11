import { ItemView, WorkspaceLeaf } from "obsidian";
import { MapPhysics } from "./map-physics";

export const CONCEPT_MAP_VIEW_TYPE = "fvsc-concept-map";
interface MapNode { term: string; evidence_count: number; source_ids: string[]; source_count: number; component_count?: number }
interface Edge { source: string; target: string; relation: string; polarity: number; modality: number; source_ids: string[] }
interface MapData {
  focus: string | null; nodes: MapNode[]; edges: Edge[]; total_neighbors: number;
  components?: string[]; suggestions?: MapNode[];
  total_edges?: number;
}
type Mode = "container" | "associations";
const NS = "http://www.w3.org/2000/svg";

export class ConceptMapView extends ItemView {
  private focusTerm?: string;
  private path: string[] = [];
  private mode: Mode = "associations";
  private requestNumber = 0;
  private frame?: number;
  private physics?: MapPhysics;
  private paused = false;
  private closed = false;

  constructor(leaf: WorkspaceLeaf, private baseUrl: () => string) { super(leaf); }
  getViewType(): string { return CONCEPT_MAP_VIEW_TYPE; }
  getDisplayText(): string { return "Карта понятий FVSC"; }
  getIcon(): string { return "git-fork"; }
  async onOpen(): Promise<void> { this.closed = false; await this.navigate(this.path, this.mode); }
  getState(): Record<string, unknown> { return { focus: this.focusTerm, path: this.path, mode: this.mode }; }
  async setState(state: Record<string, unknown>, result: { history: boolean }): Promise<void> {
    await super.setState(state, result);
    const path = Array.isArray(state.path) ? state.path.filter((t): t is string => typeof t === "string")
      : typeof state.focus === "string" ? [state.focus] : [];
    await this.navigate(path, state.mode === "associations" ? "associations" : "container");
  }
  /** Dialogue links start a new path, not an invented containment step. */
  async focus(term?: string): Promise<void> { await this.navigate(term ? [term] : [], term ? "container" : "associations"); }
  private async json(url: string, init?: RequestInit): Promise<any> {
    const response = await fetch(`${this.baseUrl()}${url}`, { ...init, signal: AbortSignal.timeout(30000) });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { detail = (await response.json()).detail ?? detail; } catch { /* keep status */ }
      throw new Error(String(detail));
    }
    return response.json();
  }
  private async navigate(path: string[], mode: Mode): Promise<void> {
    const request = ++this.requestNumber, term = path[path.length - 1];
    try {
      const url = mode === "container" && term ? `/v1/map/container?focus=${encodeURIComponent(term)}`
        : `/v1/map${term ? `?focus=${encodeURIComponent(term)}` : ""}`;
      const data = await this.json(url) as MapData;
      if (request !== this.requestNumber || this.closed) return;
      this.path = path.length ? path : data.focus ? [data.focus] : [];
      this.focusTerm = data.focus ?? undefined; this.mode = mode;
      this.render(data); this.app.workspace.requestSaveLayout();
    } catch (error) {
      if (request !== this.requestNumber || this.closed) return;
      this.stop(); this.contentEl.empty();
      this.contentEl.createEl("p", { text: `Не удалось открыть карту: ${String(error)}`, cls: "fvsc-error" });
      this.contentEl.createEl("button", { text: "Повторить" }).onclick = () => void this.navigate(path, mode);
      this.contentEl.createEl("button", { text: "К началу карты" }).onclick = () => void this.focus();
    }
  }
  private descend(term: string): void {
    const existing = this.path.indexOf(term);
    const path = this.mode === "associations" ? [term] : existing >= 0 ? this.path.slice(0, existing + 1) : [...this.path, term];
    void this.navigate(path, "container");
  }
  private render(data: MapData): void {
    this.stop(); this.contentEl.empty(); this.contentEl.addClass("fvsc-concept-map");
    const crumbs = this.contentEl.createDiv({ cls: "fvsc-map-crumbs" });
    crumbs.createEl("button", { text: "Карта" }).onclick = () => void this.focus();
    this.path.forEach((term, index) => {
      crumbs.appendText(" › ");
      crumbs.createEl("button", { text: term }).onclick = () => void this.navigate(this.path.slice(0, index + 1), "container");
    });
    const bar = this.contentEl.createDiv({ cls: "fvsc-toolbar" });
    const openInput = this.contentEl.createEl("input", { placeholder: "Открыть понятие по имени" }); openInput.maxLength = 512;
    openInput.setAttribute("aria-label", "Открыть понятие по имени");
    openInput.onkeydown = event => { if (event.key === "Enter" && openInput.value.trim()) void this.focus(openInput.value.trim()); };
    const open = this.contentEl.createEl("button", { text: "Открыть" });
    open.onclick = () => { if (openInput.value.trim()) void this.focus(openInput.value.trim()); };
    const saved = this.contentEl.createEl("select"); saved.setAttribute("aria-label", "Мои понятия");
    saved.createEl("option", { text: "Мои понятия…", value: "" });
    const renderRequest = this.requestNumber;
    void this.json("/v1/map/containers").then((terms: string[]) => {
      if (this.closed || renderRequest !== this.requestNumber) return;
      for (const term of terms) saved.createEl("option", { text: term, value: term });
    }).catch(() => { saved.disabled = true; });
    saved.onchange = () => { if (saved.value) void this.focus(saved.value); };
    const up = bar.createEl("button", { text: "↑ На уровень выше" }); up.disabled = this.path.length < 2;
    up.onclick = () => void this.navigate(this.path.slice(0, -1), "container");
    for (const [mode, label] of [["container", "Внутри понятия"], ["associations", "Связи понятия"]] as const) {
      const button = bar.createEl("button", { text: label }); button.disabled = mode === this.mode;
      button.onclick = () => void this.navigate(this.path, mode);
      if (mode === "associations" && data.nodes.find(n => n.term === data.focus)?.evidence_count === 0) button.disabled = true;
    }
    bar.createEl("button", { text: "Обновить" }).onclick = () => void this.navigate(this.path, this.mode);
    this.contentEl.createEl("h3", { text: data.focus ?? "Карта пока пуста" });
    if (!data.focus) {
      const input = this.contentEl.createEl("input", { placeholder: "Первое понятие" });
      this.contentEl.createEl("button", { text: "Открыть" }).onclick = () => { if (input.value.trim()) void this.focus(input.value.trim()); };
      return;
    }
    const inside = this.mode === "container";
    this.contentEl.createEl("p", { text: inside
      ? "Здесь — добавленные тобой составляющие понятия. Нажми на узел, чтобы раскрыть его."
      : "Связи из записей могут требовать проверки. Нажми на понятие, чтобы открыть его внутренний состав." });
    const shown = inside ? data.nodes.filter(n => n.term !== data.focus) : data.nodes;
    if (shown.length) this.draw(shown, data.edges, bar, inside);
    else this.contentEl.createEl("p", { cls: "fvsc-map-empty", text: "Состав пока не описан. Можно остановиться на этом уровне или добавить составляющие ниже." });
    if (!inside) this.contentEl.createEl("p", { text: `Показано соседей: ${Math.max(0, shown.length - 1)} из ${data.total_neighbors}` });
    if (inside) this.editor(data);
    const current = data.nodes.find(n => n.term === data.focus);
    if (current?.source_count) {
      const sources = this.contentEl.createEl("details");
      sources.createEl("summary", { text: `Исходные записи: ${current.source_count} (ссылок: ${current.source_ids.length})` });
      for (const source of current.source_ids) sources.createEl("button", { text: source }).onclick = () => void this.app.workspace.openLinkText(source, "", true);
    }
    if (data.edges.length) {
      const details = this.contentEl.createEl("details");
      details.createEl("summary", { text: `Связи из записей между показанными узлами: ${data.edges.length}${data.total_edges !== undefined ? ` из ${data.total_edges}` : ""}` });
      for (const edge of data.edges) {
        const row = details.createEl("p", { text: this.edgeLabel(edge) });
        for (const source of edge.source_ids.slice(0, 3)) row.createEl("button", { text: source }).onclick = () => void this.app.workspace.openLinkText(source, "", true);
      }
    }
  }
  private edgeLabel(edge: Edge): string { return `${edge.source} → ${edge.polarity < 0 ? "НЕ " : ""}${edge.relation} → ${edge.target} (модальность ${edge.modality})`; }
  private editor(data: MapData): void {
    const parent = data.focus!, panel = this.contentEl.createDiv({ cls: "fvsc-container-editor" });
    panel.createEl("h4", { text: "Из чего для меня состоит это понятие" });
    const input = panel.createEl("input", { placeholder: "Существующее или новое понятие" }); input.maxLength = 512;
    input.setAttribute("aria-label", "Название составляющей");
    const add = panel.createEl("button", { text: "Добавить составляющую" });
    const status = panel.createEl("p", { cls: "fvsc-error" }); status.setAttribute("role", "status");
    const change = async (child: string, present: boolean, button: HTMLButtonElement) => {
      if (!child.trim()) return;
      button.disabled = true; status.textContent = "";
      const request = this.requestNumber;
      try {
        await this.json("/v1/map/component", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ parent, child: child.trim(), present }) });
        if (request === this.requestNumber && !this.closed) await this.navigate(this.path, this.mode);
      } catch (error) { status.textContent = `Не удалось сохранить: ${String(error)}`; button.disabled = false; }
    };
    add.onclick = () => void change(input.value, true, add);
    input.onkeydown = event => { if (event.key === "Enter" && !add.disabled) void change(input.value, true, add); };
    for (const child of data.components ?? []) {
      const row = panel.createDiv({ cls: "fvsc-component-row" });
      row.createEl("button", { text: child }).onclick = () => this.descend(child);
      const remove = row.createEl("button", { text: "Убрать из состава" }); remove.onclick = () => void change(child, false, remove);
    }
    if (data.suggestions?.length) {
      const suggestions = panel.createEl("details"); suggestions.createEl("summary", { text: "Выбрать из связанных понятий" });
      suggestions.createEl("p", { text: "Это ассоциации из записей. Добавляй только то, что считаешь составляющей." });
      for (const node of data.suggestions) {
        const button = suggestions.createEl("button", { text: `+ ${node.term}` }); button.onclick = () => void change(node.term, true, button);
      }
    }
  }
  private draw(nodes: MapNode[], edges: Edge[], bar: HTMLElement, inside: boolean): void {
    const svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 900 620");
    svg.classList.add("fvsc-map-svg"); if (inside) svg.classList.add("is-container");
    svg.setAttribute("aria-label", inside ? `Внутри понятия ${this.focusTerm}` : `Связи понятия ${this.focusTerm}`);
    const world = document.createElementNS(NS, "g"); svg.append(world); this.contentEl.append(svg);
    let zoom = 1, panX = 0, panY = 0;
    const transform = () => world.setAttribute("transform", `translate(${panX},${panY}) scale(${zoom})`);
    const physics = this.physics = new MapPhysics(nodes.map(n => n.term), edges);
    const byTerm = new Map(physics.nodes.map(n => [n.term, n]));
    const lines = edges.filter(e => byTerm.has(e.source) && byTerm.has(e.target)).map(edge => {
      const line = document.createElementNS(NS, "line"); line.classList.add("fvsc-map-edge");
      if (edge.polarity < 0) line.setAttribute("stroke-dasharray", "5 4");
      const title = document.createElementNS(NS, "title"); title.textContent = this.edgeLabel(edge); line.append(title); world.append(line);
      return { line, a: byTerm.get(edge.source)!, b: byTerm.get(edge.target)! };
    });
    const groups = nodes.map(node => {
      const particle = byTerm.get(node.term)!;
      const group = document.createElementNS(NS, "g"); group.classList.add("fvsc-map-node");
      group.setAttribute("role", "button"); group.setAttribute("tabindex", "0"); group.setAttribute("aria-label", `Раскрыть ${node.term}`);
      const circle = document.createElementNS(NS, "circle"); circle.setAttribute("r", String(10 + Math.min(10, Math.sqrt(node.component_count ?? 0) * 2)));
      const label = document.createElementNS(NS, "text"); label.setAttribute("text-anchor", "middle"); label.setAttribute("y", "35");
      label.textContent = node.term.length > 23 ? `${node.term.slice(0, 22)}…` : node.term;
      const title = document.createElementNS(NS, "title"); title.textContent = `${node.term}${node.component_count !== undefined ? ` · составляющих: ${node.component_count}` : ""}`;
      group.append(circle, label, title); world.append(group);
      let dragged = false;
      group.addEventListener("click", event => { event.stopPropagation(); if (!dragged) this.descend(node.term); });
      group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); this.descend(node.term); } });
      group.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        event.stopPropagation(); dragged = false; group.setPointerCapture(event.pointerId);
        const start = { x: event.clientX, y: event.clientY }; particle.pinned = true;
        const move = (e: PointerEvent) => {
          if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 4 && !dragged) return;
          dragged = true; const p = point(e); particle.x = (p.x - panX) / zoom; particle.y = (p.y - panY) / zoom;
          physics.reheat(); render(); startAnimation();
        };
        const end = () => {
          particle.pinned = false; physics.reheat(); startAnimation();
          group.removeEventListener("pointermove", move); group.removeEventListener("pointerup", end);
          group.removeEventListener("pointercancel", cancel); group.removeEventListener("lostpointercapture", cancel);
        };
        const cancel = () => { dragged = true; end(); };
        group.addEventListener("pointermove", move); group.addEventListener("pointerup", end);
        group.addEventListener("pointercancel", cancel); group.addEventListener("lostpointercapture", cancel);
      });
      return { group, particle };
    });
    const render = () => {
      for (const { line, a, b } of lines) { line.setAttribute("x1", String(a.x)); line.setAttribute("y1", String(a.y)); line.setAttribute("x2", String(b.x)); line.setAttribute("y2", String(b.y)); }
      for (const { group, particle } of groups) group.setAttribute("transform", `translate(${particle.x},${particle.y})`);
    };
    const point = (event: MouseEvent | PointerEvent | WheelEvent) => {
      const p = svg.createSVGPoint(); p.x = event.clientX; p.y = event.clientY; return p.matrixTransform(svg.getScreenCTM()!.inverse());
    };
    const startAnimation = () => {
      if (this.paused || this.frame !== undefined || this.closed || this.physics !== physics) return;
      this.frame = requestAnimationFrame(() => { this.frame = undefined; const active = physics.tick(); render(); if (active) startAnimation(); });
    };
    const fit = () => {
      const xs = physics.nodes.map(n => n.x), ys = physics.nodes.map(n => n.y);
      const minX = Math.min(...xs) - 100, maxX = Math.max(...xs) + 100, minY = Math.min(...ys) - 80, maxY = Math.max(...ys) + 80;
      zoom = Math.min(1.5, 900 / (maxX - minX), 620 / (maxY - minY));
      panX = 450 - (minX + maxX) / 2 * zoom; panY = 310 - (minY + maxY) / 2 * zoom; transform();
    };
    for (let i = 0; i < 45; i++) physics.tick();
    render(); fit(); startAnimation();
    const pause = bar.createEl("button", { text: this.paused ? "Включить физику" : "Пауза физики" });
    pause.onclick = () => { this.paused = !this.paused; pause.textContent = this.paused ? "Включить физику" : "Пауза физики"; if (this.paused) this.stop(); else { physics.reheat(); startAnimation(); } };
    bar.createEl("button", { text: "Вместить" }).onclick = fit;
    const scale = (factor: number, x = 450, y = 310) => { const next = Math.max(0.15, Math.min(4, zoom * factor)); panX = x - (x - panX) * next / zoom; panY = y - (y - panY) * next / zoom; zoom = next; transform(); };
    bar.createEl("button", { text: "+" }).onclick = () => scale(1.2);
    bar.createEl("button", { text: "−" }).onclick = () => scale(1 / 1.2);
    svg.addEventListener("wheel", event => { event.preventDefault(); const p = point(event); scale(Math.exp(-event.deltaY * 0.001), p.x, p.y); }, { passive: false });
    svg.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      svg.setPointerCapture(event.pointerId); let last = point(event);
      const move = (e: PointerEvent) => { const p = point(e); panX += p.x - last.x; panY += p.y - last.y; last = p; transform(); };
      const end = () => { svg.removeEventListener("pointermove", move); svg.removeEventListener("pointerup", end); svg.removeEventListener("pointercancel", end); svg.removeEventListener("lostpointercapture", end); };
      svg.addEventListener("pointermove", move); svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end); svg.addEventListener("lostpointercapture", end);
    });
    this.contentEl.createEl("p", { cls: "fvsc-map-help", text: "Тяни узлы или фон · колесо — масштаб · клик — раскрыть понятие. Расстояния служат только для расположения узлов." });
  }
  private stop(): void { if (this.frame !== undefined) cancelAnimationFrame(this.frame); this.frame = undefined; }
  async onClose(): Promise<void> { this.closed = true; ++this.requestNumber; this.stop(); }
}
