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
    chunk_size = max(1, int(inputs.get("chunk_size") or 1))
    chunk_by = inputs.get("chunk_by") if inputs.get("chunk_by") is not None else "characters"
    overlap = max(0, int(inputs.get("overlap") or 0))

    if not isinstance(text, str) or text == "":
        return {"chunks": [], "chunk_count": 0}

    chunks = []

    if chunk_by == "characters":
        step = max(1, chunk_size - overlap)
        i = 0
        while i < len(text):
            chunks.append(text[i:i + chunk_size])
            i += step
    elif chunk_by == "words":
        words = text.split()
        step = max(1, chunk_size - overlap)
        i = 0
        while i < len(words):
            chunk = words[i:i + chunk_size]
            if i > 0 and len(chunk) <= overlap:
                break
            chunks.append(" ".join(chunk))
            i += step
    elif chunk_by == "sentences":
        sentences = [s.strip() for s in re.findall(r"[^.!?]+[.!?]+", text)] or [text]
        step = max(1, chunk_size - overlap)
        i = 0
        while i < len(sentences):
            chunk = sentences[i:i + chunk_size]
            if i > 0 and len(chunk) <= overlap:
                break
            chunks.append(" ".join(chunk))
            i += step

    return {
        "chunks": chunks,
        "chunk_count": len(chunks),
    }
