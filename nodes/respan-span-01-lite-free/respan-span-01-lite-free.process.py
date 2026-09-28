"""
Respan: Span-01 Lite (free) - Decision (System One) node for the zv1 engine.
"""

from typing import Any

import json

# This model scores a conversation span: {"input": [messages], "output": assistant_message},
# where every message has string content. Convert workbench conversation/message
# shapes into that; plain strings pass through; other data is sent as JSON text.
_SPAN_ROLES = {"system": "system", "developer": "system", "user": "user", "assistant": "assistant", "tool": "tool"}


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("text") is not None:
                parts.append(str(part["text"]))
            elif isinstance(part, dict) and part.get("type") == "image_url":
                parts.append("[image]")
            else:
                parts.append(json.dumps(part))
        return "\n".join(parts)
    return json.dumps(content)


def _is_message(m: Any) -> bool:
    return isinstance(m, dict) and isinstance(m.get("role"), str)


def _to_span_message(m: dict[str, Any]) -> dict[str, str]:
    text = _content_to_text(m.get("content"))
    if not text and m.get("tool_calls"):
        text = json.dumps(m["tool_calls"])
    return {"role": _SPAN_ROLES.get(m["role"], "user"), "content": text}


def _to_span_state(state: Any) -> Any:
    if isinstance(state, str):
        return state
    if _is_message(state) or (isinstance(state, list) and state and all(_is_message(m) for m in state)):
        messages = state if isinstance(state, list) else [state]
        last = messages[-1]
        if last["role"] != "assistant":
            raise ValueError(
                "this model scores a conversation span that ends with an assistant reply, "
                f"but the last message has role \"{last['role']}\". Connect a conversation "
                "ending in an assistant message, or a string."
            )
        return {"input": [_to_span_message(m) for m in messages[:-1]], "output": _to_span_message(last)}
    if isinstance(state, dict) and isinstance(state.get("input"), list) and _is_message(state.get("output")):
        return state  # already a span
    return json.dumps(state)


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Respan: Span-01 Lite (free) decision node.

    Args:
        inputs: Node inputs containing the state and a map of typed questions.
        settings: Node settings (unused for decision nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with typed answers, primary values, model, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    response = await openrouter.system_one(
        model="respan/span-01-lite:free",
        state=_to_span_state(inputs.get("state")),
        questions=inputs.get("questions"),
        node_config=node_config,
        engine_config=config,
    )

    # Primary value per answer type, for easy wiring downstream
    answers = response.get("answers") or {}
    values = {
        qid: (answer.get(answer.get("type")) if isinstance(answer, dict) else None)
        for qid, answer in answers.items()
    }

    return {
        "answers": answers,
        "values": values,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }