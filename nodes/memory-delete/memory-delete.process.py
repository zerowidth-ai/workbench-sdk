"""
Delete Memory Node - Remove a memory file that's no longer useful.
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
    result = await memory.delete(path, {"tool": "delete"})
    return {"path": path, "saved": "waiting for approval" if result.get("status") == "held" else "deleted"}
