from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    messages = inputs.get("messages")
    keep_recent = max(0, int(inputs.get("keep_recent") if inputs.get("keep_recent") is not None else 20))
    placeholder = inputs.get("placeholder") if inputs.get("placeholder") is not None else "[Truncated]"

    if not isinstance(messages, list):
        raise Exception("Messages input must be an array")

    total = len(messages)
    cutoff_index = total - keep_recent

    result = []
    truncated_count = 0

    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            result.append(message)
            continue

        # Check if this is an old tool message that should be truncated
        if message.get("role") == "tool" and i < cutoff_index:
            result.append({
                **message,
                "content": placeholder,
            })
            truncated_count += 1
        else:
            result.append({**message})

    return {
        "messages": result,
        "truncated_count": truncated_count,
    }
