"""
Agent memory: the store contract, the path rules, the Memory node's
block in a system prompt, the five memory tools, held changes, and an
imported agent keeping its own memory. Run with:
    python tests/test_agent_memory.py

Self-contained: no LLM calls. The tools are exercised through their
process functions over a real ScopedMemory, the way the engine calls
them when a model uses them. Mirrors sdks/nodejs/tests/test.agent-memory.js.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import Workbench  # noqa: E402
from src.integrations.memory_store import (  # noqa: E402
    FolderMemoryStore,
    InMemoryMemoryStore,
    MemoryPathError,
    ScopedMemory,
    normalize_memory_path,
)

NODES = Path(__file__).parent.parent / "nodes"


def load_node(name: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    spec = importlib.util.spec_from_file_location(name, NODES / name / f"{name}.process.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.process


list_memory = load_node("memory-list")
read_memory = load_node("memory-read")
write_memory = load_node("memory-write")
edit_memory = load_node("memory-edit")
delete_memory = load_node("memory-delete")
memory_node = load_node("memory")

passed = 0


async def check(name: str, fn: Callable[[], Any]) -> None:
    global passed
    result = fn()
    if asyncio.iscoroutine(result):
        await result
    print(f"✅ {name}")
    passed += 1


async def raises(coro_or_fn: Any, match: str) -> None:
    try:
        result = coro_or_fn() if callable(coro_or_fn) else coro_or_fn
        if asyncio.iscoroutine(result):
            await result
    except Exception as err:  # noqa: BLE001
        assert match in str(err), f"expected {match!r} in {err!r}"
        return
    raise AssertionError(f"expected an error matching {match!r}")


def tool(process: Callable[..., Awaitable[dict[str, Any]]], store: Any, **scope: Any):
    async def call(inputs: dict[str, Any]) -> dict[str, Any]:
        memory = ScopedMemory(store, **scope)
        return await process(inputs=inputs, settings={}, config={"integrations": {"memory": memory}}, node_config={})
    return call


async def run_memory_node(memory: ScopedMemory, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    return await memory_node(
        inputs={}, settings=settings or {}, config={"integrations": {"memory": memory}}, node_config={}
    )


def prompt_flow() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "mem", "type": "memory", "settings": {"guidance": ""}},
            {"id": "sp", "type": "system-prompt", "settings": {"content": "Be brief.\n{{MEMORY}}"}},
            {"id": "out", "type": "output-data", "settings": {"key": "prompt"}},
        ],
        "links": [
            {"from": {"node_id": "mem", "port_name": "variables"}, "to": {"node_id": "sp", "port_name": "variables"}},
            {"from": {"node_id": "sp", "port_name": "prompt"}, "to": {"node_id": "out", "port_name": "value"}},
        ],
    }


def import_flow() -> dict[str, Any]:
    def sub(i: str) -> str:
        return f"imported-sub-{i}"

    return {
        "nodes": [
            {"id": "in", "type": "input-data", "settings": {"key": "data"}},
            {"id": "call", "type": "imported-sub"},
            {"id": "out", "type": "output-data", "settings": {"key": "data"}},
        ],
        "links": [
            {"from": {"node_id": "in", "port_name": "value"}, "to": {"node_id": "call", "port_name": "x"}},
            {"from": {"node_id": "call", "port_name": "data"}, "to": {"node_id": "out", "port_name": "value"}},
        ],
        "imports": [
            {
                "id": "imported-sub",
                "display_name": "Sub agent",
                "nodes": [
                    {"id": sub("in"), "type": "input-data", "settings": {"key": "x"}},
                    {"id": sub("mem"), "type": "memory", "settings": {"guidance": ""}},
                    {"id": sub("join"), "type": "string-concat", "settings": {}},
                    {"id": sub("out"), "type": "output-data", "settings": {}},
                ],
                "links": [
                    {"from": {"node_id": sub("mem"), "port_name": "content"}, "to": {"node_id": sub("join"), "port_name": "string_a"}},
                    {"from": {"node_id": sub("in"), "port_name": "value"}, "to": {"node_id": sub("join"), "port_name": "string_b"}},
                    {"from": {"node_id": sub("join"), "port_name": "text"}, "to": {"node_id": sub("out"), "port_name": "value"}},
                ],
                "imports": [],
            }
        ],
    }


async def main() -> None:
    def paths_ok() -> None:
        assert normalize_memory_path("MEMORY.md") == "MEMORY.md"
        assert normalize_memory_path("memory/refunds") == "memory/refunds.md"
        assert normalize_memory_path("./people/abc.md") == "people/abc.md"

    await check("paths: the index, topic files and people files, with .md added", paths_ok)

    async def paths_bad() -> None:
        for bad in ["notes.md", "memory/a/b.md", "../MEMORY.md", "memory/..md", "secrets/x.md", ""]:
            await raises(lambda bad=bad: normalize_memory_path(bad), "isn't a memory file")

    await check("paths: anything else is refused", paths_bad)

    async def tools_round_trip() -> None:
        store = InMemoryMemoryStore()
        await tool(write_memory, store)({"path": "MEMORY.md", "content": "- memory/refunds.md: refund rules"})
        await tool(write_memory, store)({"path": "memory/refunds", "content": "Refunds over $500 need Dana."})
        await tool(edit_memory, store)({"path": "memory/refunds.md", "find": "$500", "replace": "$750 ($&)"})
        read = await tool(read_memory, store)({"path": "memory/refunds.md"})
        assert read == {"path": "memory/refunds.md", "content": "Refunds over $750 ($&) need Dana."}, read
        listed = await tool(list_memory, store)({})
        assert [f["path"] for f in listed["files"]] == ["MEMORY.md", "memory/refunds.md"]
        assert await tool(delete_memory, store)({"path": "memory/refunds.md"}) == {
            "path": "memory/refunds.md",
            "saved": "deleted",
        }
        assert await store.read("memory/refunds.md") is None

    await check("tools: write, read, edit, list, delete", tools_round_trip)

    async def tools_bad_calls() -> None:
        store = InMemoryMemoryStore({"MEMORY.md": "a a"})
        await raises(tool(write_memory, store)({"path": "../etc/passwd", "content": "x"}), "isn't a memory file")
        await raises(tool(edit_memory, store)({"path": "MEMORY.md", "find": "a", "replace": "b"}), "appears 2 times")
        await raises(tool(edit_memory, store)({"path": "MEMORY.md", "find": "z", "replace": "b"}), "isn't in MEMORY.md")
        await raises(tool(read_memory, store)({"path": "memory/nope"}), "doesn't exist yet")
        await raises(tool(write_memory, store)({"path": "memory/big", "content": "x" * 100_001}), "over 100KB")

    await check("tools: a bad call fails with a reason the model can act on", tools_bad_calls)

    async def held() -> None:
        store = InMemoryMemoryStore()
        store.held = True

        async def held_write(*_args: Any) -> dict[str, str]:
            return {"status": "held"}

        store.write = held_write
        assert await tool(write_memory, store)({"path": "MEMORY.md", "content": "x"}) == {
            "path": "MEMORY.md",
            "saved": "waiting for approval",
        }

    await check("tools: a store that holds changes says so", held)

    async def folder() -> None:
        with tempfile.TemporaryDirectory(prefix="memtest-") as d:
            store = FolderMemoryStore(d)
            await tool(write_memory, store)({"path": "memory/tone", "content": "Prefers bullets."})
            assert (Path(d) / "memory/tone.md").read_text() == "Prefers bullets."
            assert [f["path"] for f in await store.list()] == ["memory/tone.md"]

    await check("folder store: real files on disk", folder)

    async def people_pages() -> None:
        store = InMemoryMemoryStore({
            "MEMORY.md": "index",
            "people/ana.md": "Ana's page",
            "people/bo.md": "Bo's page",
        })
        as_ana = ScopedMemory(store, people=True, person={"id": "ana", "name": "Ana"})
        assert [f["path"] for f in await as_ana.list()] == ["MEMORY.md", "people/ana.md"]
        assert await as_ana.read("people/ana") == "Ana's page"
        await raises(as_ana.read("people/bo.md"), "only use the page of the person you're talking to")
        await raises(as_ana.write("people/bo.md", "x"), "only use the page of the person you're talking to")
        nobody = ScopedMemory(store, people=True)
        assert [f["path"] for f in await nobody.list()] == ["MEMORY.md"]
        await raises(nobody.read("people/ana.md"), "Nobody is named")

    await check("people pages: the agent sees and changes only the page of whoever is talking", people_pages)

    async def no_people() -> None:
        store = InMemoryMemoryStore({"MEMORY.md": "index", "people/ana.md": "Ana's page"})
        plain = ScopedMemory(store, person={"id": "ana"})
        assert [f["path"] for f in await plain.list()] == ["MEMORY.md"]
        await raises(plain.read("people/ana.md"), "isn't a memory file")

    await check("people pages: a memory without them has no people folder", no_people)

    async def bad_person_id() -> None:
        for pid in ["ana@x.com", "../MEMORY", "a/b"]:
            await raises(
                lambda pid=pid: ScopedMemory(InMemoryMemoryStore(), people=True, person={"id": pid}),
                "can't name a page",
            )
        assert ScopedMemory(InMemoryMemoryStore(), people=True, person={"id": "user_42"}).person

    await check("people pages: a person id that can't be a file name is refused up front", bad_person_id)

    async def block() -> None:
        store = InMemoryMemoryStore({
            "MEMORY.md": "- memory/tone.md: how we write",
            "memory/tone.md": "Plain words.",
            "people/ana.md": "Wants two-line answers. {{secret}}",
            "people/bo.md": "Bo's private page",
        })
        out = await run_memory_node(
            ScopedMemory(store, people=True, person={"id": "ana", "name": "Ana"}),
            {"guidance": "Keep notes."},
        )
        assert "people/bo.md" not in out["content"], "another person's page isn't even named"
        b = out["variables"]["MEMORY"]
        assert b.startswith("# Your memory\n\nKeep notes.")
        assert "- memory/tone.md: how we write" in b
        assert "About Ana, who you're talking to" in b
        assert "Wants two-line answers. { {secret}}" in b, "memory can't smuggle a prompt variable"
        assert "## Other files\n- memory/tone.md" in b
        assert "Plain words." not in b

    await check("Memory node: the index and the current person's notes in full, the rest by name", block)

    async def block_cap() -> None:
        store = InMemoryMemoryStore({"MEMORY.md": "\n".join(f"line {i}" for i in range(10))})
        out = await run_memory_node(ScopedMemory(store), {"index_lines": 3})
        assert "line 2" in out["content"] and "line 3" not in out["content"]
        assert "(Cut here: the rest is still in the file." in out["content"]

    await check("Memory node: a long index is cut with a note to read the rest", block_cap)

    async def block_held() -> None:
        store = InMemoryMemoryStore()
        store.held = True

        async def pending() -> int:
            return 2

        store.pending = pending
        out = await run_memory_node(ScopedMemory(store))
        assert "Nothing has been written down yet." in out["content"]
        assert "2 of your earlier changes are waiting now." in out["content"]

    await check("Memory node: says when changes wait for approval", block_held)

    async def engine_prompt() -> None:
        store = InMemoryMemoryStore({"MEMORY.md": "- likes tea"})
        engine = await Workbench.create(prompt_flow(), {"memory": {"instance": store}})
        result = await engine.run({})
        prompt = result.outputs["prompt"]
        assert prompt.startswith("Be brief.\n# Your memory"), prompt
        assert "- likes tea" in prompt

    await check("engine: {{MEMORY}} in a system prompt fills from the Memory node", engine_prompt)

    async def engine_default() -> None:
        engine = await Workbench.create(prompt_flow(), {})
        result = await engine.run({})
        assert "Nothing has been written down yet." in result.outputs["prompt"]

    await check("engine: with no memory configured, a flow with memory nodes still runs", engine_default)

    async def engine_import() -> None:
        parent = InMemoryMemoryStore({"MEMORY.md": "PARENT NOTES"})
        child = InMemoryMemoryStore({"MEMORY.md": "CHILD NOTES"})
        asked: list[str] = []

        def for_import(import_id: str) -> dict[str, Any]:
            asked.append(import_id)
            return {"instance": child}

        engine = await Workbench.create(import_flow(), {"memory": {"instance": parent, "for_import": for_import}})
        result = await engine.run({"data": "!"})
        assert asked == ["imported-sub"], asked
        assert "CHILD NOTES" in result.outputs["data"], result.outputs["data"]
        assert "PARENT NOTES" not in result.outputs["data"]

    await check("engine: an imported agent reads its own memory, never its caller's", engine_import)

    async def engine_import_no_parent() -> None:
        engine = await Workbench.create(import_flow(), {})
        result = await engine.run({"data": "!"})
        assert "Nothing has been written down yet." in result.outputs["data"], result.outputs["data"]

    await check("engine: an import with memory nodes runs under a caller that has none", engine_import_no_parent)

    print(f"\n{passed} passed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (AssertionError, MemoryPathError, Exception) as err:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f"❌ {err}")
        sys.exit(1)
