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
        filter_type = inputs.get('filter_type')
        filter_value = inputs.get('filter_value')

        if not isinstance(messages, list):
            raise Exception("Messages input must be an array")

        if not isinstance(filter_type, str) or not filter_type.strip():
            raise Exception("Filter type must be a non-empty string")

        if filter_value is None:
            raise Exception("Filter value is required")

        valid_filter_types = [
            'min_length', 'max_length', 'contains_text', 
            'starts_with', 'ends_with', 'role_equals', 'role_not_equals'
        ]

        if filter_type not in valid_filter_types:
            raise Exception(f"Invalid filter type: {filter_type}. Must be one of: {', '.join(valid_filter_types)}")

        # Helper function to extract text content from message
        def get_message_text(message):
            if not isinstance(message, dict):
                return ''
            content = message.get('content', '')
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                        text_parts.append(item['text'])
                return ' '.join(text_parts)
            else:
                return str(content)

        # Filter messages based on type
        filtered_messages = []
        for message in messages:
            if not isinstance(message, dict):
                continue

            if filter_type == 'min_length':
                min_length = int(filter_value) if isinstance(filter_value, (int, float)) else 0
                if get_message_text(message).__len__() >= min_length:
                    filtered_messages.append(message)

            elif filter_type == 'max_length':
                max_length = int(filter_value) if isinstance(filter_value, (int, float)) else 0
                if get_message_text(message).__len__() <= max_length:
                    filtered_messages.append(message)

            elif filter_type == 'contains_text':
                contains_text = str(filter_value).lower()
                if contains_text in get_message_text(message).lower():
                    filtered_messages.append(message)

            elif filter_type == 'starts_with':
                starts_with = str(filter_value).lower()
                if get_message_text(message).lower().startswith(starts_with):
                    filtered_messages.append(message)

            elif filter_type == 'ends_with':
                ends_with = str(filter_value).lower()
                if get_message_text(message).lower().endswith(ends_with):
                    filtered_messages.append(message)

            elif filter_type == 'role_equals':
                if message.get('role') == filter_value:
                    filtered_messages.append(message)

            elif filter_type == 'role_not_equals':
                if message.get('role') != filter_value:
                    filtered_messages.append(message)

        return {
            "messages": filtered_messages,
            "count": len(filtered_messages)
        }

    except Exception as error:
        print(f'Filter Messages error: {error}')
        raise Exception(f"Filter Messages error: {str(error)}")
