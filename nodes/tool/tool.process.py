from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  

  return {
    "tool": {
      "name": inputs.get("name", settings.get("name")),
      "description": inputs.get("description", settings.get("description")),
      "parameters": inputs.get("parameters", settings.get("parameters")),
      "strict": inputs.get("strict", settings.get("strict"))
    }
  }