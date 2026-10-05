"""
List Memory Node - Every file in the agent's memory with its size.
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
    files = await memory.list()
    return {"files": [{"path": f["path"], "size": f["size"]} for f in files]}
