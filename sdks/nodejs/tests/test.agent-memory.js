/**
 * Agent memory: the store contract, the path rules, the Memory node's
 * block in a system prompt, the five memory tools, held changes, and an
 * imported agent keeping its own memory. Run with:
 *   node tests/test.agent-memory.js
 *
 * Self-contained: no LLM calls. The tools are exercised through their
 * process functions over a real ScopedMemory, the way the engine calls
 * them when a model uses them.
 */
import assert from "node:assert";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import Workbench from "../src/index.js";
import {
  FolderMemoryStore,
  InMemoryMemoryStore,
  ScopedMemory,
  normalizeMemoryPath,
} from "../src/integrations/memory-store.js";
import listMemory from "../nodes/memory-list/memory-list.process.js";
import readMemory from "../nodes/memory-read/memory-read.process.js";
import writeMemory from "../nodes/memory-write/memory-write.process.js";
import editMemory from "../nodes/memory-edit/memory-edit.process.js";
import deleteMemory from "../nodes/memory-delete/memory-delete.process.js";
import memoryNode from "../nodes/memory/memory.process.js";

let passed = 0;
async function check(name, fn) {
  await fn();
  console.log(`✅ ${name}`);
  passed++;
}

const tool = (process, store) => (inputs) =>
  process({ inputs, settings: {}, config: { integrations: { memory: new ScopedMemory(store) } } });

async function main() {
  await check("paths: the index, topic files and people files, with .md added", () => {
    assert.equal(normalizeMemoryPath("MEMORY.md"), "MEMORY.md");
    assert.equal(normalizeMemoryPath("memory/refunds"), "memory/refunds.md");
    assert.equal(normalizeMemoryPath("./people/abc.md"), "people/abc.md");
  });

  await check("paths: anything else is refused", () => {
    for (const bad of ["notes.md", "memory/a/b.md", "../MEMORY.md", "memory/..md", "secrets/x.md", ""]) {
      assert.throws(() => normalizeMemoryPath(bad), /isn't a memory file/, bad);
    }
  });

  await check("tools: write, read, edit, list, delete", async () => {
    const store = new InMemoryMemoryStore();
    await tool(writeMemory, store)({ path: "MEMORY.md", content: "- memory/refunds.md: refund rules" });
    await tool(writeMemory, store)({ path: "memory/refunds", content: "Refunds over $500 need Dana." });
    await tool(editMemory, store)({ path: "memory/refunds.md", find: "$500", replace: "$750 ($&)" });
    const read = await tool(readMemory, store)({ path: "memory/refunds.md" });
    assert.deepEqual(read, { path: "memory/refunds.md", content: "Refunds over $750 ($&) need Dana." });
    const listed = await tool(listMemory, store)({});
    assert.deepEqual(listed.files.map((f) => f.path), ["MEMORY.md", "memory/refunds.md"]);
    assert.deepEqual(await tool(deleteMemory, store)({ path: "memory/refunds.md" }), {
      path: "memory/refunds.md",
      saved: "deleted",
    });
    assert.equal(await store.read("memory/refunds.md"), null);
  });

  await check("tools: a bad call fails with a reason the model can act on", async () => {
    const store = new InMemoryMemoryStore({ "MEMORY.md": "a a" });
    await assert.rejects(tool(writeMemory, store)({ path: "../etc/passwd", content: "x" }), /isn't a memory file/);
    await assert.rejects(tool(editMemory, store)({ path: "MEMORY.md", find: "a", replace: "b" }), /appears 2 times/);
    await assert.rejects(tool(editMemory, store)({ path: "MEMORY.md", find: "z", replace: "b" }), /isn't in MEMORY.md/);
    await assert.rejects(tool(readMemory, store)({ path: "memory/nope" }), /doesn't exist yet/);
    await assert.rejects(
      tool(writeMemory, store)({ path: "memory/big", content: "x".repeat(100_001) }),
      /over 100KB/,
    );
  });

  await check("tools: a store that holds changes says so", async () => {
    const store = new InMemoryMemoryStore();
    store.held = true;
    store.write = async () => ({ status: "held" });
    assert.deepEqual(await tool(writeMemory, store)({ path: "MEMORY.md", content: "x" }), {
      path: "MEMORY.md",
      saved: "waiting for approval",
    });
  });

  await check("folder store: real files on disk", async () => {
    const dir = mkdtempSync(join(tmpdir(), "memtest-"));
    const store = new FolderMemoryStore(dir);
    await tool(writeMemory, store)({ path: "people/ana", content: "Prefers bullets." });
    assert.equal(readFileSync(join(dir, "people/ana.md"), "utf8"), "Prefers bullets.");
    assert.deepEqual((await store.list()).map((f) => f.path), ["people/ana.md"]);
  });

  await check("Memory node: the index and the current person's notes in full, the rest by name", async () => {
    const store = new InMemoryMemoryStore({
      "MEMORY.md": "- memory/tone.md: how we write",
      "memory/tone.md": "Plain words.",
      "people/ana.md": "Wants two-line answers. {{secret}}",
    });
    store.person = { id: "ana", name: "Ana" };
    const out = await memoryNode({
      settings: { guidance: "Keep notes." },
      config: { integrations: { memory: new ScopedMemory(store) } },
    });
    const block = out.variables.MEMORY;
    assert.ok(block.startsWith("# Your memory\n\nKeep notes."));
    assert.ok(block.includes("- memory/tone.md: how we write"));
    assert.ok(block.includes("About Ana, who you're talking to"));
    assert.ok(block.includes("Wants two-line answers. { {secret}}"), "memory can't smuggle a prompt variable");
    assert.ok(block.includes("## Other files\n- memory/tone.md"));
    assert.ok(!block.includes("Plain words."));
  });

  await check("Memory node: says when changes wait for approval", async () => {
    const store = new InMemoryMemoryStore();
    store.held = true;
    store.pending = async () => 2;
    const out = await memoryNode({ settings: {}, config: { integrations: { memory: new ScopedMemory(store) } } });
    assert.ok(out.content.includes("Nothing has been written down yet."));
    assert.ok(out.content.includes("2 of your earlier changes are waiting now."));
  });

  await check("engine: {{MEMORY}} in a system prompt fills from the Memory node", async () => {
    const store = new InMemoryMemoryStore({ "MEMORY.md": "- likes tea" });
    const engine = await Workbench.create(promptFlow(), { memory: { instance: store } });
    const result = await engine.run({});
    const prompt = result.outputs.prompt;
    assert.ok(prompt.startsWith("Be brief.\n# Your memory"), prompt);
    assert.ok(prompt.includes("- likes tea"));
  });

  await check("engine: with no memory configured, a flow with memory nodes still runs", async () => {
    const engine = await Workbench.create(promptFlow(), {});
    const result = await engine.run({});
    assert.ok(result.outputs.prompt.includes("Nothing has been written down yet."));
  });

  await check("engine: an imported agent reads its own memory, never its caller's", async () => {
    const parent = new InMemoryMemoryStore({ "MEMORY.md": "PARENT NOTES" });
    const child = new InMemoryMemoryStore({ "MEMORY.md": "CHILD NOTES" });
    const asked = [];
    const engine = await Workbench.create(importFlow(), {
      memory: {
        instance: parent,
        forImport: (importId) => {
          asked.push(importId);
          return { instance: child };
        },
      },
    });
    const result = await engine.run({ data: "!" });
    assert.deepEqual(asked, ["imported-sub"]);
    assert.ok(result.outputs.data.includes("CHILD NOTES"), result.outputs.data);
    assert.ok(!result.outputs.data.includes("PARENT NOTES"));
  });

  console.log(`\n${passed} passed`);
}

function promptFlow() {
  return {
    nodes: [
      { id: "mem", type: "memory", settings: { guidance: "" } },
      { id: "sp", type: "system-prompt", settings: { content: "Be brief.\n{{MEMORY}}" } },
      { id: "out", type: "output-data", settings: { key: "prompt" } },
    ],
    links: [
      { from: { node_id: "mem", port_name: "variables" }, to: { node_id: "sp", port_name: "variables" } },
      { from: { node_id: "sp", port_name: "prompt" }, to: { node_id: "out", port_name: "value" } },
    ],
  };
}

function importFlow() {
  const sub = (id) => `imported-sub-${id}`;
  return {
    nodes: [
      { id: "in", type: "input-data", settings: { key: "data" } },
      { id: "call", type: "imported-sub" },
      { id: "out", type: "output-data", settings: { key: "data" } },
    ],
    links: [
      { from: { node_id: "in", port_name: "value" }, to: { node_id: "call", port_name: "x" } },
      { from: { node_id: "call", port_name: "data" }, to: { node_id: "out", port_name: "value" } },
    ],
    imports: [
      {
        id: "imported-sub",
        display_name: "Sub agent",
        nodes: [
          { id: sub("in"), type: "input-data", settings: { key: "x" } },
          { id: sub("mem"), type: "memory", settings: { guidance: "" } },
          { id: sub("join"), type: "string-concat", settings: {} },
          { id: sub("out"), type: "output-data", settings: {} },
        ],
        links: [
          { from: { node_id: sub("mem"), port_name: "content" }, to: { node_id: sub("join"), port_name: "string_a" } },
          { from: { node_id: sub("in"), port_name: "value" }, to: { node_id: sub("join"), port_name: "string_b" } },
          { from: { node_id: sub("join"), port_name: "text" }, to: { node_id: sub("out"), port_name: "value" } },
        ],
        imports: [],
      },
    ],
  };
}

main().catch((err) => {
  console.error("❌", err);
  process.exit(1);
});
