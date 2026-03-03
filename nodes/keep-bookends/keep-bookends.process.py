from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    messages = inputs.get("messages")
    keep_first = max(0, int(inputs.get("keep_first") or 0))
    keep_last = max(0, int(inputs.get("keep_last") or 0))

    if not isinstance(messages, list):
        raise Exception("Messages input must be an array")

    # Separate system messages from non-system messages
    system_messages = []
    non_system_messages = []

    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            system_messages.append(message)
        else:
            non_system_messages.append(message)

    total_non_system = len(non_system_messages)

    # If keep_first + keep_last covers everything, keep all
    if keep_first + keep_last >= total_non_system:
        return {
            "messages": messages,
            "removed_count": 0,
        }

    # Get the first N and last M non-system messages
    first_messages = non_system_messages[:keep_first]
    last_messages = non_system_messages[total_non_system - keep_last:]

    # Combine: system messages first, then first N, then last M
    result = system_messages + first_messages + last_messages
    removed_count = len(messages) - len(result)

    return {
        "messages": result,
        "removed_count": removed_count,
    }
