import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const built = ts.transpileModule(readFileSync(new URL("../src/clarification.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { sourceRangeForSelection } = await import(
  `data:text/javascript;base64,${Buffer.from(built.outputText).toString("base64")}`
);

test("Russian text offsets remain exact", () => {
  assert.deepEqual(sourceRangeForSelection("Чужая мысль", 6, 11), [6, 11]);
});

test("emoji occupies one Python code point and two browser code units", () => {
  assert.deepEqual(sourceRangeForSelection("🪶 мысль", 3, 8), [2, 7]);
  assert.deepEqual(sourceRangeForSelection("🪶 мысль", 0, 2), [0, 1]);
});

test("textarea newline normalization preserves original source offsets", () => {
  assert.deepEqual(sourceRangeForSelection("A\r\n🪶\rB", 2, 4), [3, 4]);
  assert.deepEqual(sourceRangeForSelection("A\r\n🪶\rB", 0, 6), [0, 6]);
});

test("empty, inverted and split-surrogate selections are rejected", () => {
  for (const [start, end] of [[0, 0], [2, 1], [1, 2], [0, 999]]) {
    assert.throws(() => sourceRangeForSelection("🪶", start, end));
  }
});
