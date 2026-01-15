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

        if not isinstance(messages, list):
            raise Exception("Messages input must be an array")

        swapped_messages = []

        for message in messages:
            if not message or not isinstance(message, dict):
                # Keep non-object messages as-is
                swapped_messages.append(message)
                continue

            # Create a copy of the message to avoid mutating the original
            swapped_message = message.copy()

            # Swap roles: assistant ↔ user
            if message.get('role') == 'assistant':
                swapped_message['role'] = 'user'
            elif message.get('role') == 'user':
                swapped_message['role'] = 'assistant'
            # Leave other roles (system, tool, developer) unchanged

            swapped_messages.append(swapped_message)

        return {
            'messages': swapped_messages
        }

    except Exception as error:
        raise Exception(f"Message Role Swap error: {str(error)}")
