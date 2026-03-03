from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    messages = inputs.get("messages")
    separator = inputs.get("separator") if inputs.get("separator") is not None else "\n\n"

    if not isinstance(messages, list):
        raise Exception("Messages input must be an array")

    if len(messages) == 0:
        return {
            "messages": [],
            "merged_count": 0,
        }

    def can_merge(message):
        """Check if a message can be merged."""
        if not isinstance(message, dict):
            return False
        # Tool messages are never merged
        if message.get("role") == "tool":
            return False
        # Assistant messages with tool_calls are never merged
        if message.get("role") == "assistant":
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and len(tool_calls) > 0:
                return False
        return True

    def get_content(message):
        """Extract string content from a message."""
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append(item["text"])
            return " ".join(parts)
        return str(content) if content is not None else ""

    result = []
    merged_count = 0

    for message in messages:
        if not isinstance(message, dict):
            result.append(message)
            continue

        current_can_merge = can_merge(message)

        # Check if we should merge with the previous message
        if result:
            last_message = result[-1]
            last_can_merge = can_merge(last_message)

            if (
                isinstance(last_message, dict)
                and last_can_merge
                and current_can_merge
                and message.get("role") == last_message.get("role")
            ):
                # Merge content
                last_content = get_content(last_message)
                current_content = get_content(message)
                last_message["content"] = last_content + separator + current_content
                merged_count += 1
                continue

        # Clone the message to avoid mutating input
        result.append({**message})

    return {
        "messages": result,
        "merged_count": merged_count,
    }
