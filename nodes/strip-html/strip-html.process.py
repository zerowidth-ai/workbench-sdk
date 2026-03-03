from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    html = inputs.get("html")
    preserve_line_breaks = inputs.get("preserve_line_breaks") if inputs.get("preserve_line_breaks") is not None else True
    decode_entities = inputs.get("decode_entities") if inputs.get("decode_entities") is not None else True

    if not isinstance(html, str):
        return {"text": ""}

    # Convert block-level tags to newlines if preserving line breaks
    if preserve_line_breaks:
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<(p|div|h[1-6]|li|tr)[^>]*>", "", html, flags=re.IGNORECASE)

    # Remove all HTML tags
    text = re.sub(r"<[^>]*>", "", html)

    # Decode HTML entities if requested
    if decode_entities:
        entities = {
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&apos;": "'",
            "&nbsp;": " ",
            "&copy;": "\u00A9",
            "&reg;": "\u00AE",
            "&trade;": "\u2122",
            "&mdash;": "\u2014",
            "&ndash;": "\u2013",
            "&hellip;": "\u2026",
            "&ldquo;": "\u201C",
            "&rdquo;": "\u201D",
            "&lsquo;": "\u2018",
            "&rsquo;": "\u2019",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        # Handle numeric entities
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return {"text": text}
