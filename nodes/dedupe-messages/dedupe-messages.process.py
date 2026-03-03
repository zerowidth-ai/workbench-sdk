from typing import Any
import json


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    messages = inputs.get("messages")

    if not isinstance(messages, list):
        raise Exception("Messages input must be an array")

    if len(messages) == 0:
        return {
            "messages": [],
            "removed_count": 0,
        }

    result = []
    removed_count = 0

    for message in messages:
        if not isinstance(message, dict):
            result.append(message)
            continue

        # Check if this is a duplicate of the previous message
        if result:
            last_message = result[-1]
            if isinstance(last_message, dict):
                same_role = message.get("role") == last_message.get("role")
                same_content = json.dumps(message.get("content"), sort_keys=True) == json.dumps(last_message.get("content"), sort_keys=True)

                if same_role and same_content:
                    removed_count += 1
                    continue

        result.append(message)

    return {
        "messages": result,
        "removed_count": removed_count,
    }
