"""
Run Code: the tool node over a run-scoped executor, the HTTP executor
against a local server speaking the contract, and the engine wiring.
Run with:
    python tests/test_run_code.py

Self-contained: no sandbox and no LLM. Mirrors
sdks/nodejs/tests/test.run-code.js.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Loaded by path so these checks run without the engine's own
# dependencies installed; the engine check at the end needs them.
ce = load("code_executor_under_test", ROOT / "src" / "integrations" / "code_executor.py")
run_code = load("run_code_under_test", ROOT / "nodes" / "run-code" / "run-code.process.py").process

passed = 0


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"✅ {name}")


class FakeExecutor(ce.CodeExecutorInterface):
    def __init__(self, reply=None, sessions: bool = True) -> None:
        self.reply = reply or (lambda req, n: {"stdout": "", "stderr": ""})
        self.sessions = sessions
        self.opened: list[str] = []
        self.closed: list[str] = []
        self.calls: list[dict[str, Any]] = []

    async def capabilities(self) -> dict[str, Any]:
        return {"languages": ["python"], "sessions": self.sessions, "files": True}

    async def open_session(self) -> str:
        sid = f"s{len(self.opened) + 1}"
        self.opened.append(sid)
        return sid

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(request)
        return self.reply(request, len(self.calls))


def tool(executor, settings=None):
    async def call(inputs):
        return await run_code(
            inputs=inputs,
            settings=settings or {},
            config={"integrations": {"code_executor": executor}},
            node_config={},
        )

    return call


async def expect_raises(coro, exc_type, pattern: str = "") -> str:
    try:
        await coro
    except exc_type as err:
        assert pattern in str(err), str(err)
        return str(err)
    raise AssertionError(f"expected {exc_type.__name__}")


async def main() -> None:
    fake = FakeExecutor(reply=lambda r, n: {"stdout": f"call {n}\n", "stderr": ""})
    scoped = ce.RunScopedCodeExecutor(fake)
    first = await tool(scoped)({"code": "x = 1"})
    second = await tool(scoped)({"code": "print(x)"})
    assert (first["stdout"], second["stdout"]) == ("call 1\n", "call 2\n")
    assert fake.opened == ["s1"]
    assert [c["session"] for c in fake.calls] == ["s1", "s1"]
    assert fake.calls[0]["timeoutMs"] == 60000 and fake.calls[0]["language"] == "python"
    await scoped.close()
    await scoped.close()
    assert fake.closed == ["s1"]
    ok("one session for the whole run, closed once at the end")

    fake = FakeExecutor(sessions=False)
    await tool(ce.RunScopedCodeExecutor(fake))({"code": "1"})
    assert fake.opened == [] and "session" not in fake.calls[0]
    ok("an executor without sessions runs every call fresh")

    fake = FakeExecutor(
        reply=lambda r, n: {
            "stdout": "before\n",
            "stderr": "ZeroDivisionError: division by zero",
            "error": {"kind": "runtime", "message": "ZeroDivisionError"},
        }
    )
    out = await tool(ce.RunScopedCodeExecutor(fake))({"code": "1/0"})
    assert "ZeroDivisionError" in out["stderr"] and out["stdout"] == "before\n"
    ok("a failure in the code comes back as output, not an error")

    fake = FakeExecutor(
        reply=lambda r, n: {"stdout": "step 1\n", "stderr": "", "error": {"kind": "timeout", "message": "t"}}
    )
    message = await expect_raises(
        tool(ce.RunScopedCodeExecutor(fake), {"timeout_seconds": 5})({"code": "while True: pass"}),
        RuntimeError,
        "5s limit",
    )
    assert "step 1" in message and fake.calls[0]["timeoutMs"] == 5000
    ok("the time limit stops the call with a reason and what it printed")

    fake = FakeExecutor(
        reply=lambda r, n: {
            "stdout": "",
            "stderr": "",
            "files": [
                {"path": "chart.png", "mimeType": "image/png", "data": "iVBORw0KGgo=", "size": 8},
                {"path": "out.csv", "mimeType": "text/csv", "data": "YSxiCg==", "size": 4},
            ],
        }
    )
    out = await tool(ce.RunScopedCodeExecutor(fake))({"code": "plot()"})
    assert out["content"] == [{"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"}]
    assert out["files"] == [
        {"path": "chart.png", "mimeType": "image/png", "size": 8},
        {"path": "out.csv", "mimeType": "text/csv", "size": 4},
    ]
    ok("images reach the model as content; file listings carry no bytes")

    fake = FakeExecutor(
        reply=lambda r, n: {"stdout": "", "stderr": "", "error": {"kind": "session_lost", "message": "gone"}}
        if n == 2
        else {"stdout": "", "stderr": ""}
    )
    run = tool(ce.RunScopedCodeExecutor(fake))
    await run({"code": "a = 1"})
    await expect_raises(run({"code": "print(a)"}), ce.CodeSessionLostError)
    await run({"code": "a = 1"})
    assert fake.opened == ["s1", "s2"]
    ok("a lost session says so, and the next call starts a new one")

    fake = FakeExecutor(reply=lambda r, n: {"stdout": "x" * 50000, "stderr": ""})
    out = await tool(ce.RunScopedCodeExecutor(fake))({"code": "print('x' * 50000)"})
    assert len(out["stdout"]) < 21000 and "cut: 30000 more characters" in out["stdout"]
    ok("output is capped before it reaches the conversation")

    fake = FakeExecutor()
    await expect_raises(
        tool(ce.RunScopedCodeExecutor(fake))({"code": "1", "language": "javascript"}),
        ValueError,
        "runs python, not javascript",
    )
    assert fake.calls == []
    ok("a language the sandbox doesn't run is refused before it's sent")

    await expect_raises(
        run_code(inputs={"code": "1"}, settings={}, config={"integrations": {}}, node_config={}),
        ValueError,
        "No sandbox is available",
    )
    await expect_raises(tool(ce.RunScopedCodeExecutor(FakeExecutor()))({"code": "  "}), ValueError, "no code")
    ok("no executor and no code each fail with a reason")

    fake = FakeExecutor()
    await tool(ce.RunScopedCodeExecutor(fake), {"timeout_seconds": 600})({"code": "1"})
    assert fake.calls[0]["timeoutMs"] == 120000
    ok("the time limit is held to 120 seconds")

    fake = FakeExecutor(reply=lambda r, n: {"stdout": "", "stderr": "", "result": [1] * 20000})
    out = await tool(ce.RunScopedCodeExecutor(fake))({"code": "[1] * 20000"})
    assert isinstance(out["result"], str) and "more characters" in out["result"]
    fake = FakeExecutor(reply=lambda r, n: {"stdout": "", "stderr": "", "result": {"a": [1, 2]}})
    assert (await tool(ce.RunScopedCodeExecutor(fake))({"code": "x"}))["result"] == {"a": [1, 2]}
    ok("a big result is capped like printed output; a small one is left alone")

    huge = "A" * (8 * 1024 * 1024)
    fake = FakeExecutor(
        reply=lambda r, n: {
            "stdout": "",
            "stderr": "",
            "files": [{"path": "big.png", "mimeType": "image/png", "data": huge}]
            + [{"path": f"p{i}.png", "mimeType": "image/png", "data": "iVBO"} for i in range(5)],
        }
    )
    out = await tool(ce.RunScopedCodeExecutor(fake))({"code": "plots()"})
    assert len(out["content"]) == 4 and all(c["data"] == "iVBO" for c in out["content"])
    assert len(out["files"]) == 6 and out["stderr"].startswith("2 images not shown")
    ok("at most four images reach the model; the rest are listed and noted")

    seen: list[tuple[str, str, str]] = []
    run_ids: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, status: int, data: Any = None) -> None:
            body = b"" if data is None else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = json.loads(self.rfile.read(length) or b"null") if length else None
            seen.append((self.command, self.path, self.headers.get("authorization") or ""))
            run_ids.append(self.headers.get("x-run") or "")
            if self.command == "POST" and self.path == "/sessions":
                return self._send(200, {"id": "abc"})
            if self.command == "POST" and self.path == "/run":
                if body["code"] == "lost":
                    return self._send(410, {"error": {"kind": "session_lost", "message": "gone"}})
                return self._send(200, {"stdout": f"ran in {body.get('session')}\n", "stderr": ""})
            if self.command == "DELETE" and self.path == "/sessions/abc":
                self.send_response(204)
                return self.end_headers()
            self._send(404, {"error": "no"})

        do_POST = _handle
        do_DELETE = _handle

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        async def get_headers():
            return {"x-run": "r1"}

        scoped = ce.create_code_executor({"url": url, "api_key": "k1", "get_headers": get_headers})
        out = await scoped.run(language="python", code="print(1)", timeout_ms=1000)
        assert out["stdout"] == "ran in abc\n"
        await expect_raises(scoped.run(language="python", code="lost", timeout_ms=1000), ce.CodeSessionLostError)
        assert scoped.session_id is None
        await scoped.run(language="python", code="print(2)", timeout_ms=1000)
        await scoped.close()
        assert [f"{m} {p}" for m, p, _ in seen] == [
            "POST /sessions",
            "POST /run",
            "POST /run",
            "POST /sessions",
            "POST /run",
            "DELETE /sessions/abc",
        ]
        assert all(auth == "Bearer k1" for _, _, auth in seen)
        assert all(r == "r1" for r in run_ids)
    finally:
        server.shutdown()
    ok("HTTP executor: the contract's paths, bearer key, get_headers, and 410 as a lost session")

    try:
        from src import Workbench  # noqa: E402
        from src.integrations.code_executor import RunScopedCodeExecutor
    except ImportError as err:
        print(f"⏭  engine check skipped: the engine's dependencies aren't installed ({err})")
    else:
        flow = json.loads((ROOT / "tests" / "flows" / "flow.addition.json").read_text())["flow"]
        fake = FakeExecutor()
        engine = await Workbench.create(flow, {"code_executor": {"instance": fake}})
        executor = engine.config["integrations"]["code_executor"]
        assert isinstance(executor, RunScopedCodeExecutor)
        await executor.run(language="python", code="1", timeout_ms=1000)
        await engine.cleanup()
        assert fake.closed == ["s1"]
        ok("engine: config code_executor becomes the integration, and cleanup closes the session")

        fake = FakeExecutor()
        engine = await Workbench.create(flow, {"code_executor": {"instance": fake}})
        executor = engine.config["integrations"]["code_executor"]
        inputs = json.loads((ROOT / "tests" / "flows" / "flow.addition.json").read_text())["inputs"]
        for _ in range(2):
            await executor.run(language="python", code="1", timeout_ms=1000)
            await engine.run(inputs)
        assert fake.opened == ["s1", "s2"] and fake.closed == ["s1", "s2"]
        ok("engine: each run() of a reused engine gets its own session")

        fixture = json.loads((ROOT / "tests" / "flows" / "flow.addition-import-inline.json").read_text())
        fake = FakeExecutor()
        during: list[Any] = []
        holder: dict[str, Any] = {}
        engine = await Workbench.create(
            fixture["flow"],
            {
                "code_executor": {"instance": fake},
                "on_node_complete": lambda _e: during.append(holder["executor"].session_id),
            },
        )
        holder["executor"] = engine.config["integrations"]["code_executor"]
        await holder["executor"].run(language="python", code="x = 1", timeout_ms=1000)
        await engine.run(fixture["inputs"])
        assert during and all(sid == "s1" for sid in during), f"caller's session during the run: {during}"
        assert fake.closed == ["s1"]
        ok("engine: an imported flow leaves its caller's session open")

    print(f"\n{passed} run-code checks passed")


if __name__ == "__main__":
    asyncio.run(main())
