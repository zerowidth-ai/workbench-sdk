from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    This node simply returns the tools array injected by the engine.
    The engine should set settings['tools'] to the array of tool schemas/runners.
    """
    return {
        "tools": settings.get("tools", [])
    }
