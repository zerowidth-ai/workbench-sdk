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

        separator = settings.get('separator', ' ')
        preserve_structure = settings.get('preserve_structure', True)

        if len(messages) == 0:
            return {
                "messages": [],
                "original_count": 0,
                "merged_count": 0,
                "merges_performed": 0
            }

        # Helper function to merge content
        def merge_content(content1, content2):
            if isinstance(content1, str) and isinstance(content2, str):
                return content1 + separator + content2
            elif isinstance(content1, list) and isinstance(content2, list):
                if preserve_structure:
                    # Preserve multi-modal structure
                    return content1 + content2
                else:
                    # Flatten to text
                    text1 = ''.join([item['text'] for item in content1 if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item])
                    text2 = ''.join([item['text'] for item in content2 if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item])
                    return text1 + separator + text2
            elif isinstance(content1, str) and isinstance(content2, list):
                if preserve_structure:
                    return [{'type': 'text', 'text': content1}] + content2
                else:
                    text2 = ''.join([item['text'] for item in content2 if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item])
                    return content1 + separator + text2
            elif isinstance(content1, list) and isinstance(content2, str):
                if preserve_structure:
                    return content1 + [{'type': 'text', 'text': content2}]
                else:
                    text1 = ''.join([item['text'] for item in content1 if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item])
                    return text1 + separator + content2
            else:
                # Fallback - convert to strings
                return str(content1) + separator + str(content2)

        result = []
        merges_performed = 0
        current_message = None

        for message in messages:
            if not isinstance(message, dict) or 'role' not in message:
                # Invalid message - add as-is
                if current_message:
                    result.append(current_message)
                    current_message = None
                result.append(message)
                continue

            if current_message is None:
                # Start new message
                current_message = message.copy()
            elif current_message['role'] == message['role']:
                # Same role - merge content
                current_message['content'] = merge_content(current_message['content'], message['content'])
                merges_performed += 1
            else:
                # Different role - finish current message and start new one
                result.append(current_message)
                current_message = message.copy()

        # Add the last message if there is one
        if current_message:
            result.append(current_message)

        return {
            "messages": result,
            "original_count": len(messages),
            "merged_count": len(result),
            "merges_performed": merges_performed
        }

    except Exception as error:
        print(f'Merge Messages error: {error}')
        raise Exception(f"Merge Messages error: {str(error)}")
