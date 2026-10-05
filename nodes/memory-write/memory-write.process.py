"""
Write Memory Node - Create a memory file or replace its whole content.
"""

from typing import Any


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
    path = memory.normalize(inputs.get("path"))
    content = inputs.get("content")
    result = await memory.write(path, "" if content is None else str(content), {"tool": "write"})
    return {"path": path, "saved": "waiting for approval" if result.get("status") == "held" else "saved"}
