"""
Prompt caching for models that need to be told where to cache.

Anthropic models cache a request's prefix only up to blocks marked
``cache_control: {"type": "ephemeral"}``, at most four per request.
Everything before a mark (tools, then the system prompt, then the
messages) is reused by the next call that starts the same way, read at a
fraction of the input price. Other providers OpenRouter serves cache a
repeated prefix on their own.

Marks come from two places: the System Prompt node marks the end of the
prompt's fixed part, and this adds one on the last user message so
earlier turns are cached for the next call. Marks a caller placed itself
count too; past four, the latest are dropped. For a model that doesn't
take marks, or with caching off, every mark is removed.

Mirrors ``sdks/nodejs/src/utilities/promptCache.js``.
"""

from __future__ import annotations

from typing import Any

MAX_MARKS = 4


def takes_cache_marks(model: Any) -> bool:
    """Models that cache only where they're told to."""
    return isinstance(model, str) and model.startswith("anthropic/")


def read_cache_usage(usage: Any) -> dict[str, int]:
    """Prompt-cache counts from a usage block (``prompt_tokens_details``),
    which OpenRouter normalizes every provider to. Both are part of
    ``prompt_tokens``. Accepts a dict or an SDK usage object."""
    if usage is None:
        return {"cached_tokens": 0, "cache_write_tokens": 0}
    details = usage.get("prompt_tokens_details") if isinstance(usage, dict) else getattr(usage, "prompt_tokens_details", None)
    if details is None and not isinstance(usage, dict):
        extra = getattr(usage, "model_extra", None) or {}
        details = extra.get("prompt_tokens_details")

    def field(name: str) -> int:
        if details is None:
            return 0
        value = details.get(name) if isinstance(details, dict) else getattr(details, name, None)
        if value is None and not isinstance(details, dict):
            value = (getattr(details, "model_extra", None) or {}).get(name)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    return {"cached_tokens": field("cached_tokens"), "cache_write_tokens": field("cache_write_tokens")}


def apply_prompt_cache(messages: Any, *, model: Any, enabled: bool = True) -> Any:
    """The messages to send, with cache marks placed for a model that takes
    them and removed for any other. Never mutates the input."""
    if not isinstance(messages, list):
        return messages
    marking = enabled and takes_cache_marks(model)

    kept = 0
    out: list[Any] = []
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list) or not any(isinstance(b, dict) and b.get("cache_control") for b in content):
            out.append(message)
            continue
        blocks = []
        for block in content:
            if not isinstance(block, dict) or not block.get("cache_control"):
                blocks.append(block)
                continue
            empty_text = block.get("type") == "text" and not block.get("text")
            if marking and kept < MAX_MARKS and not empty_text:
                kept += 1
                blocks.append(block)
            else:
                blocks.append({k: v for k, v in block.items() if k != "cache_control"})
        out.append({**message, "content": blocks})

    if not marking or kept >= MAX_MARKS:
        return out

    for i in range(len(out) - 1, -1, -1):
        message = out[i]
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            blocks = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            blocks = list(content)
        else:
            break
        if any(isinstance(b, dict) and b.get("cache_control") for b in blocks):
            break
        for j in range(len(blocks) - 1, -1, -1):
            block = blocks[j]
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                blocks[j] = {**block, "cache_control": {"type": "ephemeral"}}
                out[i] = {**message, "content": blocks}
                break
        break
    return out
