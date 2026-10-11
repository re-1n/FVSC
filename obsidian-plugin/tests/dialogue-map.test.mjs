import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, realpathSync } from "node:fs";
import { createHash } from "node:crypto";
import vm from "node:vm";
import ts from "typescript";

function load(file, dependencies) {
  const js = ts.transpileModule(readFileSync(new URL(file, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const context = { exports: {}, require: name => {
    if (!(name in dependencies)) throw new Error(`Unexpected dependency ${name}`);
    return dependencies[name];
  }, process, console, AbortSignal, setTimeout, clearTimeout, fetch: (...args) => dependencies.fetch(...args) };
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
