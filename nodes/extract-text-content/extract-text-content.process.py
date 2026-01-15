from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        input_data = inputs.get('input')
        if not input_data:
            raise Exception("Input is required for text extraction")

        include_role = settings.get('include_role', False)
        role_format = settings.get('role_format', '{role}: ')
        separator = settings.get('separator', '\n\n')

        # Helper function to extract text from content
        def extract_text_from_content(content):
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text = ''
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                        text += item['text']
                return text
            else:
                return str(content or '')

        # Helper function to format role prefix
        def format_role_prefix(role):
            if not include_role or not role:
                return ''
            return role_format.replace('{role}', role.upper())

        extracted_texts = []
        message_count = 0

        if isinstance(input_data, str):
            # Direct string input
            extracted_texts.append(input_data)
            message_count = 1
        elif isinstance(input_data, list):
            # Array of messages
            for message in input_data:
                if isinstance(message, str):
                    # String message - no role assumption
                    extracted_texts.append(message)
                    message_count += 1
                elif isinstance(message, dict) and 'content' in message:
                    # Message object
                    text = extract_text_from_content(message['content'])
                    if text.strip():
                        role_prefix = format_role_prefix(message.get('role'))
                        extracted_texts.append(role_prefix + text)
                        message_count += 1
        elif isinstance(input_data, dict) and 'content' in input_data:
            # Single message object
            text = extract_text_from_content(input_data['content'])
            if text.strip():
                role_prefix = format_role_prefix(input_data.get('role'))
                extracted_texts.append(role_prefix + text)
                message_count = 1
        else:
            # Fallback for other types
            text = str(input_data)
            extracted_texts.append(text)
            message_count = 1

        result = separator.join(extracted_texts)

        return {
            "text": result,
            "message_count": message_count
        }

    except Exception as error:
        print(f'Extract Text Content error: {error}')
        raise Exception(f"Extract Text Content error: {str(error)}")
