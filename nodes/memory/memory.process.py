"""
Memory Node - Reads the agent's memory into a block for the system prompt.

Only MEMORY.md and the current person's notes ride along in full; every
other file is named so the agent can read it when it matters. The store
comes from the host as config["integrations"]["memory"].
"""

import re
from typing import Any, Optional

INDEX = "MEMORY.md"
INDEX_BYTE_CAP = 25000
PERSON_BYTE_CAP = 8000


def _cap(content: str, max_bytes: int, max_lines: Optional[int] = None) -> str:
    out = content
    if max_lines:
        lines = out.split("\n")
        if len(lines) > max_lines:
            out = "\n".join(lines[:max_lines])
    encoded = out.encode("utf-8")
    if len(encoded) > max_bytes:
        out = encoded[:max_bytes].decode("utf-8", errors="ignore")
    if len(out) < len(content):
        return f"{out}\n\n(Cut here: the rest is still in the file. Read the file for it.)"
    return out


def _inert(text: str) -> str:
    """A memory line must never read as a prompt {{variable}} downstream."""
    return re.sub(r"\{\{", "{ {", text)


def _file_block(path: str, content: str) -> str:
    return f'<memory-file path="{path}">\n{_inert(content)}\n</memory-file>'


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    memory = (config.get("integrations") or {}).get("memory")
    if not memory:
        raise ValueError("No memory is available. Pass config['memory'] to the engine.")

    settings = settings or {}
    variable_name = settings.get("variable_name") or "MEMORY"
    guidance = settings.get("guidance") or ""
    try:
        index_lines = int(settings.get("index_lines") or 200)
    except (TypeError, ValueError):
        index_lines = 200

    files = await memory.list()
    paths = {f["path"] for f in files}
    person = memory.person
    person_path = f"people/{person['id']}.md" if person and person.get("id") else None

    sections = ["# Your memory"]
    if guidance.strip():
        sections.append(guidance.strip())

    index = await memory.read(INDEX) if INDEX in paths else None
    sections.append(
        f"## {INDEX}\n{_file_block(INDEX, _cap(index, INDEX_BYTE_CAP, index_lines))}"
        if index
        else f"## {INDEX}\nEmpty. Nothing has been written down yet."
    )

    if person_path:
        name = person.get("name") or person["id"]
        notes = await memory.read(person_path) if person_path in paths else None
        sections.append(
            f"## About {name}, who you're talking to\n{_file_block(person_path, _cap(notes, PERSON_BYTE_CAP))}"
            if notes
            else f"## About {name}, who you're talking to\nNo notes yet. How {name} likes to work with you goes in {person_path}."
        )

    others = [f["path"] for f in files if f["path"] not in (INDEX, person_path)]
    if others:
        sections.append("## Other files\n" + "\n".join(f"- {p}" for p in others))

    if memory.held:
        waiting = await memory.pending()
        note = "Changes you make to memory wait for a person to approve them before they take effect."
        if waiting > 0:
            note += f" {waiting} of your earlier changes are waiting now."
        sections.append(note)

    content = "\n\n".join(sections)
    return {
        "variables": {variable_name: content},
        "content": content,
        "files": [{"path": f["path"], "size": f["size"]} for f in files],
    }
