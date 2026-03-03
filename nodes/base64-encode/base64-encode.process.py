from typing import Any
import base64


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")

    if not isinstance(text, str):
        return {"encoded": ""}

    encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")

    return {"encoded": encoded}
