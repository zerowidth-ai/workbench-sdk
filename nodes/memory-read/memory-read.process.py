"""
Read Memory Node - Open one file from the agent's memory.
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
    content = await memory.read(path)
    if content is None:
        raise ValueError(f"{path} doesn't exist yet.")
    return {"path": path, "content": content}
