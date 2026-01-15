from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        messages = inputs.get('messages')
        start = inputs.get('start')
        end = inputs.get('end')

        if not isinstance(messages, list):
            raise Exception("Messages input must be an array")

        if not isinstance(start, int) or start < 0:
            raise Exception("Start index must be a non-negative integer")

        if not isinstance(end, int):
            raise Exception("End index must be an integer")

        # Handle -1 as end of array
        if end == -1:
            end = len(messages)

        if end < start:
            raise Exception("End index must be greater than or equal to start index")

        # Clamp indices to array bounds
        start = max(0, min(start, len(messages)))
        end = max(start, min(end, len(messages)))

        # Extract messages in range
        range_messages = messages[start:end]

        return {
            "messages": range_messages,
            "count": len(range_messages)
        }

    except Exception as error:
        print(f'Get Messages Range error: {error}')
        raise Exception(f"Get Messages Range error: {str(error)}")
