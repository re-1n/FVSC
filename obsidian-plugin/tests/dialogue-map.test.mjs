import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, realpathSync } from "node:fs";
import { createHash } from "node:crypto";
import vm from "node:vm";
import ts from "typescript";

function load(file, dependencies, globals = {}) {
  const js = ts.transpileModule(readFileSync(new URL(file, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const context = { exports: {}, require: name => {
    if (!(name in dependencies)) throw new Error(`Unexpected dependency ${name}`);
    return dependencies[name];
  }, process, console, AbortSignal, setTimeout, clearTimeout, fetch: (...args) => dependencies.fetch(...args), ...globals };
  vm.runInNewContext(js, context);
  return context.exports;
}

test("concept links preserve text and navigate only after an explicit click", async () => {
  const { AntourageView } = load("../src/view.ts", {
    obsidian: { ItemView: class {}, Notice: class {} }, "./bootstrap": {}, "./clarification": {},
  });
  const view = Object.create(AntourageView.prototype);
  const navigations = [];
  view.getPlugin = () => ({ focusConcept: term => navigations.push(term) });
  view.fetchJson = async () => [[{text: "Свобода", term: "свобода"}, {text: " <script>literal</script>", term: null}]];
  const children = [];
  const element = {isConnected: true, empty: () => { children.length = 0; },
    appendText: text => children.push({text}), createEl: (_tag, options) => {
      const child = {text: options.text}; children.push(child); return child;
    }};
  await view.linkConcepts([{ element, text: "Свобода <script>literal</script>" }]);
  assert.deepEqual(navigations, []);
  assert.equal(children.map(c => c.text).join(""), "Свобода <script>literal</script>");
  children[0].onclick();
  assert.deepEqual(navigations, ["свобода"]);
});

function backend(fetcher) {
  let spawned = 0;
  const { BackendController } = load("../src/backend.ts", {
    obsidian: { Notice: class {} }, crypto: {createHash}, fs: {realpathSync},
    child_process: {spawn: () => { spawned++; throw new Error("Must not spawn"); }}, fetch: fetcher,
  });
  const status = [];
  const controller = new BackendController(() => ({port: 8768, pythonPath: "python", fvscRepoPath: "."}),
    {vaultPath: process.cwd(), onStatus: s => status.push(s)});
  return {controller, status, spawned: () => spawned};
}

test("existing matching vault service is reused and not stopped by plugin", async () => {
  let path = realpathSync(process.cwd());
  if (process.platform === "win32") path = path.toLowerCase();
  const id = createHash("sha256").update(path).digest("hex");
  const item = backend(async () => ({ok: true, json: async () => ({configured: true, vault_id: id})}));
  await item.controller.start();
  assert.equal(item.controller.getStatus(), "up");
  assert.equal(item.spawned(), 0);
  await item.controller.stop();
  assert.equal(item.controller.getStatus(), "stopped");
});

test("a service for another vault is never adopted", async () => {
  const item = backend(async () => ({ok: true, json: async () => ({configured: true, vault_id: "other"})}));
  await item.controller.start();
  assert.equal(item.controller.getStatus(), "failed");
  assert.equal(item.spawned(), 0);
});

test("physics settles, keeps finite positions, respects dragging and separates nodes", () => {
  const { MapPhysics } = load("../src/map-physics.ts", {});
  const physics = new MapPhysics(Array.from({length: 100}, (_, i) => String(i)),
    Array.from({length: 99}, (_, i) => ({source: "0", target: String(i + 1)})));
  physics.nodes[0].pinned = true;
  const initial = {x: physics.nodes[0].x, y: physics.nodes[0].y};
  let ticks = 0;
  while (physics.tick() && ticks < 1000) ticks++;
  assert.ok(ticks < 1000);
  assert.deepEqual({x: physics.nodes[0].x, y: physics.nodes[0].y}, initial);
  for (const node of physics.nodes) assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y));
  const other = physics.nodes[1];
  assert.ok(Math.hypot(other.x - initial.x, other.y - initial.y) > 40);
  physics.reheat(); assert.equal(physics.tick(), true);
});

test("recursive navigation preserves a containment path, folds cycles, and resets for associations", async () => {
  const { ConceptMapView } = load("../src/map-view.ts", {obsidian: {ItemView: class {}}, "./map-physics": {}});
  const view = Object.create(ConceptMapView.prototype);
  const paths = [];
  view.navigate = async (path, mode) => paths.push({path: Array.from(path), mode});
  view.path = ["freedom", "choice"]; view.mode = "container";
  view.descend("possibility");
  view.descend("freedom");
  view.mode = "associations"; view.descend("other");
  await view.focus("external link");
  assert.deepEqual(paths, [
    {path: ["freedom", "choice", "possibility"], mode: "container"},
    {path: ["freedom"], mode: "container"},
    {path: ["other"], mode: "container"},
    {path: ["external link"], mode: "container"},
  ]);
});

test("map dragging does not navigate, clicking does, and closing cancels animation", async () => {
  class Element {
    children = []; listeners = new Map(); attributes = {}; classList = {add() {}};
    setAttribute(key, value) { this.attributes[key] = value; }
    append(...children) { this.children.push(...children); }
    createEl(tag, options) { const e = new Element(); e.tag = tag; e.options = options; this.append(e); return e; }
    addEventListener(type, callback) { const list = this.listeners.get(type) ?? []; list.push(callback); this.listeners.set(type, list); }
    removeEventListener(type, callback) { this.listeners.set(type, (this.listeners.get(type) ?? []).filter(f => f !== callback)); }
    fire(type, extra = {}) { for (const fn of [...(this.listeners.get(type) ?? [])]) fn({button: 0, pointerId: 1, clientX: 100, clientY: 100, stopPropagation() {}, preventDefault() {}, ...extra}); }
    setPointerCapture() {}
    getScreenCTM() { return {inverse() { return {}; }}; }
    createSVGPoint() { return {x: 0, y: 0, matrixTransform() { return {x: this.x, y: this.y}; }}; }
  }
  const { MapPhysics } = load("../src/map-physics.ts", {});
  let requested = 0, cancelled = 0;
  const { ConceptMapView } = load("../src/map-view.ts", {obsidian: {ItemView: class {}}, "./map-physics": {MapPhysics}}, {
    document: {createElementNS: (_ns, tag) => { const e = new Element(); e.tag = tag; return e; }},
    requestAnimationFrame: () => ++requested, cancelAnimationFrame: () => cancelled++,
  });
  const view = Object.create(ConceptMapView.prototype);
  view.contentEl = new Element(); view.path = ["parent"]; view.mode = "container"; view.requestNumber = 0;
  const navigations = []; view.descend = term => navigations.push(term);
  view.draw([{term: "child", source_ids: [], source_count: 0}], [], new Element(), true);
  const svg = view.contentEl.children[0], group = svg.children[0].children[0];
  assert.equal(requested, 1); assert.deepEqual(navigations, []);
  group.fire("pointerdown"); group.fire("pointermove", {clientX: 140}); group.fire("pointerup"); group.fire("click");
  assert.deepEqual(navigations, []);
  group.fire("pointerdown"); group.fire("pointerup"); group.fire("click");
  assert.deepEqual(navigations, ["child"]);
  await view.onClose(); assert.equal(cancelled, 1);
});
