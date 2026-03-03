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
    collapse_spaces = inputs.get("collapse_spaces") if inputs.get("collapse_spaces") is not None else True
    collapse_newlines = inputs.get("collapse_newlines") if inputs.get("collapse_newlines") is not None else True
    trim = inputs.get("trim") if inputs.get("trim") is not None else True
    trim_lines = inputs.get("trim_lines") if inputs.get("trim_lines") is not None else False

    if not isinstance(text, str):
        return {"text": ""}

    # Trim each line if requested
    if trim_lines:
        text = "\n".join(line.strip() for line in text.split("\n"))

    # Collapse multiple newlines into single newline
    if collapse_newlines:
        text = re.sub(r"\n{2,}", "\n", text)

    # Collapse multiple spaces into single space
    if collapse_spaces:
        text = re.sub(r"[ \t]{2,}", " ", text)

    # Trim leading and trailing whitespace
    if trim:
        text = text.strip()

    return {"text": text}
