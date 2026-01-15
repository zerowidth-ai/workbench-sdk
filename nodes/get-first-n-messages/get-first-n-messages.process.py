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
        count = inputs.get('count')

        if not isinstance(messages, list):
            raise Exception("Messages input must be an array")

        if not isinstance(count, int) or count < 0:
            raise Exception("Count must be a non-negative integer")

        # Get the first N messages
        first_messages = messages[:count] if count > 0 else []
        actual_count = len(first_messages)

        return {
            "messages": first_messages,
            "count": actual_count
        }

    except Exception as error:
        print(f'Get First N Messages error: {error}')
        raise Exception(f"Get First N Messages error: {str(error)}")
