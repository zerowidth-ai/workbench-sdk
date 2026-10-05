"""
Edit Memory Node - Replace one exact piece of text in a memory file.
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
    current = await memory.read(path)
    if current is None:
        raise ValueError(f"{path} doesn't exist yet. Write it to create it.")

    find = "" if inputs.get("find") is None else str(inputs["find"])
    hits = current.count(find) if find else 0
    if hits == 0:
        raise ValueError(f"That text isn't in {path}.")
    if hits > 1:
        raise ValueError(f"That text appears {hits} times in {path}; include more of the line.")

    replace = "" if inputs.get("replace") is None else str(inputs["replace"])
    result = await memory.write(path, current.replace(find, replace, 1), {"tool": "edit"})
    return {"path": path, "saved": "waiting for approval" if result.get("status") == "held" else "saved"}
