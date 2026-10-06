"""
Prompt caching for models that need to be told where to cache.

Anthropic models cache a request's prefix only up to blocks marked
``cache_control: {"type": "ephemeral"}``, at most four per request.
Everything before a mark (tools, then the system prompt, then the
messages) is reused by the next call that starts the same way, read at a
fraction of the input price. Other providers OpenRouter serves cache a
repeated prefix on their own.

Where marks go, for a model that takes them:

- the end of the system prompt's fixed part. The System Prompt node
  records it as ``cache_prefix_length`` on its text block (the text before
  the first variable it fills in); the block is split there and the first
  part marked, so a value that changes per run doesn't spoil the cache;
- marks the caller placed itself (``cache_control`` on a block);
- the last message, whatever its role, so everything so far (earlier
  turns, and this turn's tool calls and results) is reused by the next
  call.

At most four: the earliest three are kept, then the last message. A mark
that comes before a one-hour mark gets the one-hour lifetime too, since
Anthropic needs longer-lived marks to come first. For any other model, or
with caching off, the hint and every mark are removed.

Mirrors ``sdks/nodejs/src/utilities/promptCache.js``.
"""

from __future__ import annotations

from typing import Any

MAX_MARKS = 4
MARK = {"type": "ephemeral"}


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


def _is_text(block: Any) -> bool:
    return isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)


def _strip(block: Any) -> Any:
    if not isinstance(block, dict) or ("cache_control" not in block and "cache_prefix_length" not in block):
        return block
    return {k: v for k, v in block.items() if k not in ("cache_control", "cache_prefix_length")}


def _split_at_prefix(blocks: list[Any]) -> list[Any]:
    """One message's blocks, with the System Prompt node's hint turned into
    a split and a mark."""
    out: list[Any] = []
    for b in blocks:
        at = b.get("cache_prefix_length") if _is_text(b) else None
        if not isinstance(at, int) or isinstance(at, bool):
            out.append(b)
            continue
        block = {k: v for k, v in b.items() if k != "cache_prefix_length"}
        text = b["text"]
        if at <= 0 or not text[:at].strip():
            out.append(block)
        elif at >= len(text):
            out.append({**block, "cache_control": block.get("cache_control") or dict(MARK)})
        else:
            out.append({"type": "text", "text": text[:at], "cache_control": dict(MARK)})
            out.append({**block, "text": text[at:]})
    return out


def _strip_message(m: Any) -> Any:
    if isinstance(m, dict) and isinstance(m.get("content"), list):
        return {**m, "content": [_strip(b) for b in m["content"]]}
    return m


def strip_cache_hints(value: Any) -> Any:
    """A message or conversation with every cache mark and hint removed, for
    anything that sends one somewhere other than a chat model (a decision
    model's ``state``). Anything else passes through. Never mutates the
    input."""
    return [_strip_message(m) for m in value] if isinstance(value, list) else _strip_message(value)


def _has_mark(message: Any, test: Any) -> bool:
    content = message.get("content") if isinstance(message, dict) else None
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("cache_control") and test(b["cache_control"]) for b in content)


def apply_prompt_cache(messages: Any, *, model: Any, enabled: bool = True) -> Any:
    """The messages to send, with cache marks placed for a model that takes
    them and removed for any other. Never mutates the input."""
    if not isinstance(messages, list):
        return messages
    marking = enabled and takes_cache_marks(model)

    def content_of(m: Any) -> Any:
        return m.get("content") if isinstance(m, dict) else None

    if not marking:
        return [_strip_message(m) for m in messages]

    # Split the hinted blocks, then keep the earliest three marks.
    kept = 0
    out: list[Any] = []
    for m in messages:
        content = content_of(m)
        if not isinstance(content, list):
            out.append(m)
            continue
        blocks = []
        for b in _split_at_prefix(content):
            if not isinstance(b, dict) or not b.get("cache_control"):
                blocks.append(b)
            # A mark on an empty block is refused by the provider.
            elif kept < MAX_MARKS - 1 and not (_is_text(b) and not b["text"]):
                kept += 1
                blocks.append(b)
            else:
                blocks.append(_strip(b))
        out.append({**m, "content": blocks})

    # The last message's last text block.
    if out and isinstance(out[-1], dict) and out[-1].get("role") != "system":
        m = out[-1]
        content = m.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else list(content) if isinstance(content, list) else None
        if blocks is not None and not any(isinstance(b, dict) and b.get("cache_control") for b in blocks):
            for j in range(len(blocks) - 1, -1, -1):
                if _is_text(blocks[j]) and blocks[j]["text"]:
                    blocks[j] = {**blocks[j], "cache_control": dict(MARK)}
                    out[-1] = {**m, "content": blocks}
                    break

    # Longer-lived marks must come first: anything before a one-hour mark
    # lives an hour too.
    last_hour = max((i for i, m in enumerate(out) if _has_mark(m, lambda c: c.get("ttl") == "1h")), default=-1)
    for i in range(last_hour):
        m = out[i]
        if not _has_mark(m, lambda c: c.get("ttl") != "1h"):
            continue
        out[i] = {
            **m,
            "content": [
                {**b, "cache_control": {**b["cache_control"], "ttl": "1h"}}
                if isinstance(b, dict) and b.get("cache_control") and b["cache_control"].get("ttl") != "1h"
                else b
                for b in m["content"]
            ],
        }
    return out
