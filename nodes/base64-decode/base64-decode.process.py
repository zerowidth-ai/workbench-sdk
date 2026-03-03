from typing import Any
import base64


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    encoded = inputs.get("encoded")

    if not isinstance(encoded, str):
        return {"text": "", "success": False, "error": "Input must be a string"}

    if encoded == "":
        return {"text": "", "success": True, "error": None}

    try:
        text = base64.b64decode(encoded).decode("utf-8")
        return {"text": text, "success": True, "error": None}
    except Exception as e:
        return {"text": "", "success": False, "error": str(e)}
