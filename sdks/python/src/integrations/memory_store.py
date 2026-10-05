"""
Agent memory: a small folder of markdown an agent reads and writes
between conversations.

    MEMORY.md            a short index, read into the prompt every turn
    memory/<topic>.md    detail, read when the agent decides it needs it
    people/<id>.md       optional: one person's private page in a shared
                         memory, read in only when they're talking

A memory store is four operations over those paths. The SDK ships a
folder store and an in-memory store; a host keeping many agents'
memories implements the same four over whatever it has (SQL rows,
bucket objects, Redis) and passes it as ``config["memory"]["instance"]``.
Each store instance is one memory: the host decides whose (an agent's
own, one end user's) before handing it to the engine.

The memory nodes (Memory, memory_list/read/write/edit/delete) only ever
talk to ``config["integrations"]["memory"]``, which is the host's store
wrapped in ``ScopedMemory`` so every store gets the same path rules and
size limits.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_INDEX = "MEMORY.md"
MAX_FILE_BYTES = 100_000
MAX_FILES = 200

_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)

# The node types that read or write an agent's memory.
MEMORY_NODE_TYPES = frozenset({
    "memory",
    "memory-list",
    "memory-read",
    "memory-write",
    "memory-edit",
    "memory-delete",
})


def flow_uses_memory(flow: dict[str, Any] | None) -> bool:
    nodes = (flow or {}).get("nodes")
    return isinstance(nodes, list) and any(n.get("type") in MEMORY_NODE_TYPES for n in nodes)


class MemoryPathError(ValueError):
    pass


def normalize_memory_path(raw: Any) -> str:
    """
    Normalize and check a memory path. Accepts ``MEMORY.md``,
    ``memory/<name>.md`` and ``people/<id>.md``, adding ``.md`` when
    missing. Nothing nests deeper than one folder.
    """
    trimmed = re.sub(r"^\.?/+", "", str(raw if raw is not None else "").strip())
    with_ext = trimmed if re.search(r"\.md$", trimmed, re.IGNORECASE) else f"{trimmed}.md"
    parts = with_ext.split("/")
    ok = (len(parts) == 1 and parts[0] == MEMORY_INDEX) or (
        len(parts) == 2
        and parts[0] in ("memory", "people")
        and bool(_SEGMENT.match(parts[1]))
        and ".." not in parts[1]
    )
    if not ok:
        raise MemoryPathError(
            f'"{raw}" isn\'t a memory file. Use MEMORY.md, memory/<topic>.md, or people/<id>.md.'
        )
    return with_ext


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class MemoryStoreInterface:
    """
    The contract every memory store implements. Paths arrive already
    normalized. ``origin`` says which node made the change, for stores
    that keep a history.

    Optional members a host store may add:
        held       True when changes wait for a person to approve them;
                   write/delete then return {"status": "held"}.
        pending()  how many changes are waiting, for the prompt.
    """

    async def list(self) -> list[dict[str, Any]]:
        """Every file: [{"path", "size", "updated_at"?}]."""
        raise NotImplementedError("list() must be implemented by a memory store")

    async def read(self, path: str) -> str | None:
        """The file's content, or None when it doesn't exist."""
        raise NotImplementedError("read() must be implemented by a memory store")

    async def write(self, path: str, content: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        """{"status": "applied" | "held"}"""
        raise NotImplementedError("write() must be implemented by a memory store")

    async def delete(self, path: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        """{"status": "applied" | "held"}"""
        raise NotImplementedError("delete() must be implemented by a memory store")


class InMemoryMemoryStore(MemoryStoreInterface):
    """Memory that lasts as long as the process. For tests and trials."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files: dict[str, str] = dict(files or {})

    async def list(self) -> list[dict[str, Any]]:
        return [
            {"path": p, "size": len(content.encode("utf-8"))}
            for p, content in sorted(self.files.items())
        ]

    async def read(self, path: str) -> str | None:
        return self.files.get(path)

    async def write(self, path: str, content: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        self.files[path] = content
        return {"status": "applied"}

    async def delete(self, path: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        self.files.pop(path, None)
        return {"status": "applied"}


class FolderMemoryStore(MemoryStoreInterface):
    """Memory as real files under a folder: ``<root>/MEMORY.md``, …"""

    def __init__(self, root: str | Path) -> None:
        if not root:
            raise ValueError("FolderMemoryStore needs a folder path.")
        self.root = Path(root).resolve()

    async def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        candidates = [self.root / MEMORY_INDEX]
        for folder in ("memory", "people"):
            if (self.root / folder).is_dir():
                candidates.extend((self.root / folder).iterdir())
        for full in candidates:
            if not full.is_file() or not full.name.endswith(".md"):
                continue
            rel = full.relative_to(self.root).as_posix()
            try:
                normalize_memory_path(rel)
            except MemoryPathError:
                continue
            stat = full.stat()
            out.append({
                "path": rel,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            })
        return sorted(out, key=lambda f: f["path"])

    async def read(self, path: str) -> str | None:
        try:
            return (self.root / path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    async def write(self, path: str, content: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return {"status": "applied"}

    async def delete(self, path: str, origin: dict[str, Any] | None = None) -> dict[str, str]:
        (self.root / path).unlink(missing_ok=True)
        return {"status": "applied"}


class ScopedMemory:
    """
    The store the memory nodes see: path rules and size limits in front
    of whatever store the host passed, so a custom store can't be handed
    ``../../etc/passwd`` and doesn't have to re-implement the limits.

    People pages (``people=True``, a shared memory with a page per
    person): the agent sees and changes only the page of whoever is
    talking (``person``), so one person's notes never reach another
    conversation. With nobody talking it sees no pages at all. Without
    ``people``, the ``people/`` folder isn't part of the memory.
    """

    def __init__(self, store: Any, *, people: bool = False, person: dict[str, Any] | None = None) -> None:
        self.store = store
        self.people = people is True
        person_id = (person or {}).get("id")
        self.talking: dict[str, str] | None = (
            {"id": str(person_id), "name": (person or {}).get("name") or str(person_id)}
            if self.people and person_id
            else None
        )
        # The id becomes a file name; an id that can't be one would leave
        # the agent pointed at a page it isn't allowed to write.
        if self.talking and (
            not _SEGMENT.match(f"{self.talking['id']}.md") or ".." in self.talking["id"]
        ):
            raise MemoryPathError(
                f'memory person id "{self.talking["id"]}" can\'t name a page: use letters, digits, '
                '".", "_" and "-" (hash or slug an email first).'
            )

    @property
    def person(self) -> dict[str, str] | None:
        """Whoever is talking, when this memory keeps a page per person."""
        return self.talking

    @property
    def held(self) -> bool:
        return getattr(self.store, "held", False) is True

    def normalize(self, raw: Any) -> str:
        """The canonical form of a path the agent may use, or a MemoryPathError."""
        p = normalize_memory_path(raw)
        if not p.startswith("people/"):
            return p
        if not self.people:
            raise MemoryPathError(f'"{raw}" isn\'t a memory file. Use MEMORY.md or memory/<topic>.md.')
        if not self.talking or p != f"people/{self.talking['id']}.md":
            raise MemoryPathError(
                f"You can only use the page of the person you're talking to: people/{self.talking['id']}.md."
                if self.talking
                else "Nobody is named in this conversation, so there's no person's page to use."
            )
        return p

    async def pending(self) -> int:
        fn = getattr(self.store, "pending", None)
        return await _maybe_await(fn()) if callable(fn) else 0

    async def list(self) -> list[dict[str, Any]]:
        own = f"people/{self.talking['id']}.md" if self.talking else None
        files = await _maybe_await(self.store.list())
        return [f for f in files if not f["path"].startswith("people/") or f["path"] == own]

    async def read(self, raw: Any) -> str | None:
        return await _maybe_await(self.store.read(self.normalize(raw)))

    async def write(self, raw: Any, content: Any, origin: dict[str, Any] | None = None) -> dict[str, str]:
        p = self.normalize(raw)
        text = "" if content is None else str(content)
        if len(text.encode("utf-8")) > MAX_FILE_BYTES:
            raise MemoryPathError(
                f"{p} would be over {MAX_FILE_BYTES // 1000}KB. Keep memory files short; "
                "split detail into another topic file."
            )
        existing = await _maybe_await(self.store.list())
        if not any(f["path"] == p for f in existing) and len(existing) >= MAX_FILES:
            raise MemoryPathError(
                f"Memory already holds {MAX_FILES} files. Fold some together or delete ones "
                "that no longer matter."
            )
        return await _maybe_await(self.store.write(p, text, origin or {}))

    async def delete(self, raw: Any, origin: dict[str, Any] | None = None) -> dict[str, str]:
        return await _maybe_await(self.store.delete(self.normalize(raw), origin or {}))


def create_memory(memory_config: dict[str, Any] | None = None) -> ScopedMemory:
    """
    Pick the memory for a run from ``config["memory"]``:
        {"instance": ...}  a host store (wins)
        {"path": ...}      a FolderMemoryStore at that folder
        neither            an in-memory store, gone when the process exits
    plus ``people: True`` and ``person: {"id", "name"}`` for a shared
    memory with a page per person.
    """
    memory_config = memory_config or {}
    options = {"people": memory_config.get("people"), "person": memory_config.get("person")}
    if memory_config.get("instance") is not None:
        return ScopedMemory(memory_config["instance"], **options)
    if memory_config.get("path"):
        return ScopedMemory(FolderMemoryStore(memory_config["path"]), **options)
    return ScopedMemory(InMemoryMemoryStore(), **options)
