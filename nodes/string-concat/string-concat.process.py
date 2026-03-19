from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  a = str(inputs.get("string_a", "")) if inputs.get("string_a") is not None else ""
  b = str(inputs.get("string_b", "")) if inputs.get("string_b") is not None else ""

  return {
    "text": f"{a}{b}"
  }