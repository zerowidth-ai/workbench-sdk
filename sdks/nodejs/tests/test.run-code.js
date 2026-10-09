/**
 * Run Code: the tool node over a run-scoped executor, the HTTP executor
 * against a local server speaking the contract, and the engine wiring
 * (config.codeExecutor in, session closed by cleanup). Run with:
 *   node tests/test.run-code.js
 *
 * Self-contained: no sandbox and no LLM. The fake executor records what
 * the tool asked of it.
 */
import assert from "node:assert";
import http from "node:http";
import { readFileSync } from "node:fs";
import path from "node:path";

import Workbench from "../src/index.js";
import {
  CodeExecutorInterface,
  CodeSessionLostError,
  HttpCodeExecutor,
  RunScopedCodeExecutor,
} from "../src/integrations/code-executor.js";
import runCode from "../nodes/run-code/run-code.process.js";
import { getDirname } from "../src/utilities/helpers.js";

let passed = 0;
async function check(name, fn) {
  await fn();
  console.log(`✅ ${name}`);
  passed++;
}

class FakeExecutor extends CodeExecutorInterface {
  constructor({ reply, sessions = true } = {}) {
    super();
    this.reply = reply ?? (() => ({ stdout: "", stderr: "" }));
    this.sessions = sessions;
    this.opened = [];
    this.closed = [];
    this.calls = [];
  }
  async capabilities() {
    return { languages: ["python"], sessions: this.sessions, files: true };
  }
  async openSession() {
    const id = `s${this.opened.length + 1}`;
    this.opened.push(id);
    return id;
  }
  async closeSession(id) {
    this.closed.push(id);
  }
  async run(request) {
    this.calls.push(request);
    return this.reply(request, this.calls.length);
  }
}

const tool = (executor, settings = {}) => (inputs) =>
  runCode({ inputs, settings, config: { integrations: { codeExecutor: executor } } });

async function main() {
  await check("one session for the whole run, closed once at the end", async () => {
    const fake = new FakeExecutor({ reply: (_r, n) => ({ stdout: `call ${n}\n`, stderr: "" }) });
    const scoped = new RunScopedCodeExecutor(fake);
    const run = tool(scoped);
    const first = await run({ code: "x = 1\nprint('call 1')" });
    const second = await run({ code: "print(x)" });
    assert.equal(first.stdout, "call 1\n");
    assert.equal(second.stdout, "call 2\n");
    assert.deepEqual(fake.opened, ["s1"]);
    assert.deepEqual(fake.calls.map((c) => c.session), ["s1", "s1"]);
    assert.equal(fake.calls[0].language, "python");
    assert.equal(fake.calls[0].timeoutMs, 60000);
    await scoped.close();
    await scoped.close();
    assert.deepEqual(fake.closed, ["s1"]);
  });

  await check("an executor without sessions runs every call fresh", async () => {
    const fake = new FakeExecutor({ sessions: false });
    await tool(new RunScopedCodeExecutor(fake))({ code: "1" });
    assert.deepEqual(fake.opened, []);
    assert.equal(fake.calls[0].session, undefined);
  });

  await check("a failure in the code comes back as output, not an error", async () => {
    const fake = new FakeExecutor({
      reply: () => ({
        stdout: "before\n",
        stderr: "Traceback (most recent call last):\nZeroDivisionError: division by zero",
        error: { kind: "runtime", message: "ZeroDivisionError" },
      }),
    });
    const out = await tool(new RunScopedCodeExecutor(fake))({ code: "1/0" });
    assert.match(out.stderr, /ZeroDivisionError/);
    assert.equal(out.stdout, "before\n");
  });

  await check("the time limit stops the call with a reason and what it printed", async () => {
    const fake = new FakeExecutor({
      reply: () => ({ stdout: "step 1\n", stderr: "", error: { kind: "timeout", message: "timed out" } }),
    });
    await assert.rejects(
      tool(new RunScopedCodeExecutor(fake), { timeout_seconds: 5 })({ code: "while True: pass" }),
      (err) => /5s limit/.test(err.message) && /step 1/.test(err.message)
    );
    assert.equal(fake.calls[0].timeoutMs, 5000);
  });

  await check("images reach the model as content; file listings carry no bytes", async () => {
    const fake = new FakeExecutor({
      reply: () => ({
        stdout: "",
        stderr: "",
        files: [
          { path: "chart.png", mimeType: "image/png", data: "iVBORw0KGgo=", size: 8 },
          { path: "out.csv", mimeType: "text/csv", data: "YSxiCg==", size: 4, url: "https://files.example/out.csv" },
        ],
      }),
    });
    const out = await tool(new RunScopedCodeExecutor(fake))({ code: "plot()" });
    assert.deepEqual(out.content, [{ type: "image", data: "iVBORw0KGgo=", mimeType: "image/png" }]);
    assert.deepEqual(out.files, [
      { path: "chart.png", mimeType: "image/png", size: 8 },
      { path: "out.csv", mimeType: "text/csv", size: 4, url: "https://files.example/out.csv" },
    ]);
  });

  await check("a lost session says so, and the next call starts a new one", async () => {
    const fake = new FakeExecutor({
      reply: (_r, n) =>
        n === 2 ? { stdout: "", stderr: "", error: { kind: "session_lost", message: "gone" } } : { stdout: "", stderr: "" },
    });
    const run = tool(new RunScopedCodeExecutor(fake));
    await run({ code: "a = 1" });
    await assert.rejects(run({ code: "print(a)" }), CodeSessionLostError);
    await run({ code: "a = 1" });
    assert.deepEqual(fake.opened, ["s1", "s2"]);
  });

  await check("output is capped before it reaches the conversation", async () => {
    const fake = new FakeExecutor({ reply: () => ({ stdout: "x".repeat(50000), stderr: "" }) });
    const out = await tool(new RunScopedCodeExecutor(fake))({ code: "print('x' * 50000)" });
    assert.ok(out.stdout.length < 21000);
    assert.match(out.stdout, /cut: 30000 more characters/);
  });

  await check("a language the sandbox doesn't run is refused before it's sent", async () => {
    const fake = new FakeExecutor();
    await assert.rejects(
      tool(new RunScopedCodeExecutor(fake))({ code: "1", language: "javascript" }),
      /runs python, not javascript/
    );
    assert.equal(fake.calls.length, 0);
  });

  await check("no executor and no code each fail with a reason", async () => {
    await assert.rejects(
      runCode({ inputs: { code: "1" }, settings: {}, config: { integrations: {} } }),
      /No sandbox is available/
    );
    await assert.rejects(tool(new RunScopedCodeExecutor(new FakeExecutor()))({ code: "  " }), /no code/);
  });

  await check("the time limit is held to 120 seconds", async () => {
    const fake = new FakeExecutor();
    await tool(new RunScopedCodeExecutor(fake), { timeout_seconds: 600 })({ code: "1" });
    assert.equal(fake.calls[0].timeoutMs, 120000);
  });

  await check("a big result is capped like printed output; a small one is left alone", async () => {
    const big = new FakeExecutor({ reply: () => ({ stdout: "", stderr: "", result: Array(20000).fill(1) }) });
    const out = await tool(new RunScopedCodeExecutor(big))({ code: "list(range(20000))" });
    assert.equal(typeof out.result, "string");
    assert.match(out.result, /cut: \d+ more characters/);
    const small = new FakeExecutor({ reply: () => ({ stdout: "", stderr: "", result: { a: [1, 2] } }) });
    assert.deepEqual((await tool(new RunScopedCodeExecutor(small))({ code: "x" })).result, { a: [1, 2] });
  });

  await check("at most four images reach the model; the rest are listed and noted", async () => {
    const huge = "A".repeat(8 * 1024 * 1024);
    const fake = new FakeExecutor({
      reply: () => ({
        stdout: "",
        stderr: "",
        files: [
          { path: "big.png", mimeType: "image/png", data: huge },
          ...[1, 2, 3, 4, 5].map((n) => ({ path: `p${n}.png`, mimeType: "image/png", data: "iVBO" })),
        ],
      }),
    });
    const out = await tool(new RunScopedCodeExecutor(fake))({ code: "plots()" });
    assert.equal(out.content.length, 4);
    assert.ok(out.content.every((c) => c.data === "iVBO"));
    assert.equal(out.files.length, 6);
    assert.match(out.stderr, /^2 images not shown/);
  });

  await check("the run's signal reaches the HTTP request", async () => {
    const seen = [];
    const fetchImpl = async (url, init) => {
      seen.push({ url, signal: init.signal });
      return new Response(JSON.stringify(url.endsWith("/sessions") ? { id: "x" } : { stdout: "", stderr: "" }));
    };
    const controller = new AbortController();
    const scoped = new RunScopedCodeExecutor(new HttpCodeExecutor({ url: "http://sandbox", fetch: fetchImpl }));
    await runCode({
      inputs: { code: "1" },
      settings: {},
      config: { integrations: { codeExecutor: scoped }, signal: controller.signal },
    });
    const run = seen.filter((s) => s.url.endsWith("/run"));
    assert.equal(run[0].signal, controller.signal);
  });

  await check("HTTP executor: the contract's paths, bearer key, and 410 as a lost session", async () => {
    const seen = [];
    const server = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        seen.push({ method: req.method, url: req.url, auth: req.headers.authorization, body });
        const send = (status, data) => {
          res.writeHead(status, { "content-type": "application/json" });
          res.end(data === undefined ? "" : JSON.stringify(data));
        };
        if (req.method === "POST" && req.url === "/sessions") return send(200, { id: "abc" });
        if (req.method === "POST" && req.url === "/run") {
          const parsed = JSON.parse(body);
          if (parsed.code === "lost") return send(410, { error: { kind: "session_lost", message: "gone" } });
          return send(200, { stdout: `ran in ${parsed.session}\n`, stderr: "" });
        }
        if (req.method === "DELETE" && req.url === "/sessions/abc") {
          res.writeHead(204);
          return res.end();
        }
        send(404, { error: "no" });
      });
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address();
    try {
      const scoped = new RunScopedCodeExecutor(
        new HttpCodeExecutor({ url: `http://127.0.0.1:${port}/`, apiKey: "k1" })
      );
      const out = await scoped.run({ language: "python", code: "print(1)", timeoutMs: 1000 });
      assert.equal(out.stdout, "ran in abc\n");
      await assert.rejects(scoped.run({ language: "python", code: "lost", timeoutMs: 1000 }), CodeSessionLostError);
      assert.equal(scoped.sessionId, null);
      await scoped.run({ language: "python", code: "print(2)", timeoutMs: 1000 });
      await scoped.close();
      assert.deepEqual(
        seen.map((s) => `${s.method} ${s.url}`),
        ["POST /sessions", "POST /run", "POST /run", "POST /sessions", "POST /run", "DELETE /sessions/abc"]
      );
      assert.ok(seen.every((s) => s.auth === "Bearer k1"));
    } finally {
      server.close();
    }
  });

  const fixture = (name) => JSON.parse(readFileSync(path.join(getDirname(import.meta.url), "flows", name), "utf8"));

  await check("engine: config.codeExecutor becomes the integration, and cleanup closes the session", async () => {
    const { flow } = fixture("flow.addition.json");
    const fake = new FakeExecutor();
    const engine = await Workbench.create(flow, { codeExecutor: { instance: fake } });
    const executor = engine.config.integrations.codeExecutor;
    assert.ok(executor instanceof RunScopedCodeExecutor);
    await executor.run({ language: "python", code: "1", timeoutMs: 1000 });
    await engine.cleanup();
    assert.deepEqual(fake.closed, ["s1"]);
  });

  await check("engine: each run() of a reused engine gets its own session", async () => {
    const { flow, inputs } = fixture("flow.addition.json");
    const fake = new FakeExecutor();
    const engine = await Workbench.create(flow, { codeExecutor: { instance: fake } });
    const executor = engine.config.integrations.codeExecutor;
    for (const _ of [1, 2]) {
      await executor.run({ language: "python", code: "1", timeoutMs: 1000 });
      await engine.run(inputs);
    }
    assert.deepEqual(fake.opened, ["s1", "s2"]);
    assert.deepEqual(fake.closed, ["s1", "s2"]);
  });

  await check("engine: an imported flow leaves its caller's session open", async () => {
    const { flow, inputs } = fixture("flow.addition-import-inline.json");
    const fake = new FakeExecutor();
    const during = [];
    const engine = await Workbench.create(flow, {
      codeExecutor: { instance: fake },
      onNodeComplete: () => during.push(engine.config.integrations.codeExecutor.sessionId),
    });
    await engine.config.integrations.codeExecutor.run({ language: "python", code: "x = 1", timeoutMs: 1000 });
    await engine.run(inputs);
    assert.ok(during.length > 0);
    assert.ok(during.every((id) => id === "s1"), `caller's session during the run: ${during}`);
    assert.deepEqual(fake.closed, ["s1"]);
  });

  console.log(`\n${passed} run-code checks passed`);
}

main().catch((err) => {
  console.error("❌", err);
  process.exit(1);
});
