from typing import Any


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

    result = []
    inserted_count = 0
    pending_tool_calls = []  # List of {"id": tool_call_id} to track order

    for message in messages:
        if not isinstance(message, dict):
            result.append(message)
            continue

        role = message.get("role")

        # If this is an assistant message with tool_calls, track them
        if role == "assistant":
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and len(tool_calls) > 0:
                # First, handle any previously pending tool calls
                if pending_tool_calls:
                    for pending in pending_tool_calls:
                        result.append({
                            "role": "tool",
                            "tool_call_id": pending["id"],
                            "content": "Tool call was not executed",
                        })
                        inserted_count += 1
                    pending_tool_calls = []

                result.append(message)

                # Track the new tool calls in order
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and tool_call.get("id"):
                        pending_tool_calls.append({"id": tool_call["id"]})
                continue

        # If this is a tool response, mark that tool_call_id as handled
        if role == "tool" and message.get("tool_call_id"):
            tool_call_id = message["tool_call_id"]
            pending_index = -1
            for i, pending in enumerate(pending_tool_calls):
                if pending["id"] == tool_call_id:
                    pending_index = i
                    break

            if pending_index != -1:
                # Insert synthetic responses for any tool calls that come before this one
                for i in range(pending_index):
                    result.append({
                        "role": "tool",
                        "tool_call_id": pending_tool_calls[i]["id"],
                        "content": "Tool call was not executed",
                    })
                    inserted_count += 1
                # Remove handled tool calls (the ones we just backfilled + the current one)
                pending_tool_calls = pending_tool_calls[pending_index + 1:]

            result.append(message)
            continue

        # If this is a user message, we need to backfill any pending tool calls first
        if role == "user":
            for pending in pending_tool_calls:
                result.append({
                    "role": "tool",
                    "tool_call_id": pending["id"],
                    "content": "Tool call was not executed",
                })
                inserted_count += 1
            pending_tool_calls = []
            result.append(message)
            continue

        # For any other message type, just pass through
        result.append(message)

    # Handle any remaining pending tool calls at the end of the conversation
    for pending in pending_tool_calls:
        result.append({
            "role": "tool",
            "tool_call_id": pending["id"],
            "content": "Tool call was not executed",
        })
        inserted_count += 1

    return {
        "messages": result,
        "inserted_count": inserted_count,
    }
