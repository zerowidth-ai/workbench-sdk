"""
Input Chat Node - Accepts chat messages as input to the conversation flow.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Input Chat node.
    Simply passes through the messages.
    The engine handles individual processing due to process_individually: true
    """
    messages = settings.get("messages", [])
    message_text = None

    if len(messages) > 0:
        # Get the most recent message
        most_recent_message = messages[-1]

        # Get the text content of the most recent message
        # content will either be a string or an array of objects
        # where one object might have a type: "text" and a text property
        message_text = most_recent_message.get("content")

        if isinstance(message_text, list):
            # Find the text content item
            text_item = next(
                (item for item in message_text if item.get("type") == "text"),
                None
            )
            message_text = text_item.get("text") if text_item else None

        # If message_text is empty, set to None
        if not message_text or message_text == "":
            message_text = None

    # For each message, remove the id, participant_id and timestamp fields
    cleaned_messages = []
    for message in messages:
        cleaned_message = {k: v for k, v in message.items()
                          if k not in ("id", "participant_id", "timestamp")}
        cleaned_messages.append(cleaned_message)

    return {
        "messages": cleaned_messages,
        "message": message_text,
    }
