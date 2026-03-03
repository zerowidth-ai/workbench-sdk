from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")
    return_all = inputs.get("return_all") if inputs.get("return_all") is not None else False
    language_filter = inputs.get("language_filter")
    if language_filter:
        language_filter = language_filter.lower().strip()
    else:
        language_filter = None

    if not isinstance(text, str) or text.strip() == "":
        return {"code": None, "language": None, "found": False, "blocks": []}

    blocks = []

    # Match markdown code blocks with optional language
    code_block_regex = r"```(\w*)\n?([\s\S]*?)```"

    for match in re.finditer(code_block_regex, text):
        language = match.group(1).strip().lower() if match.group(1) else None
        code = match.group(2)

        # Apply language filter if specified
        if language_filter:
            if language != language_filter:
                continue

        blocks.append({
            "code": code,
            "language": language if language else None,
        })

    if len(blocks) == 0:
        return {"code": None, "language": None, "found": False, "blocks": []}

    if return_all:
        return {
            "code": [b["code"] for b in blocks],
            "language": blocks[0]["language"],
            "found": True,
            "blocks": blocks,
        }

    return {
        "code": blocks[0]["code"],
        "language": blocks[0]["language"],
        "found": True,
        "blocks": blocks,
    }
