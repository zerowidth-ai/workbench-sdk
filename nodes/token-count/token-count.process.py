import tiktoken
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
            raise Exception("Input is required for token counting")

        # Get the tokenizer setting, default to cl200k_base
        tokenizer = settings.get('tokenizer', 'cl200k_base')

        # Validate tokenizer option
        if tokenizer not in ['cl200k_base', 'cl100k_base']:
            raise Exception(f"Unsupported tokenizer: {tokenizer}. Only cl200k_base and cl100k_base are supported.")

        # Get the encoding for the specified tokenizer
        # Python tiktoken uses different names
        encoding_name = 'cl200k_base' if tokenizer == 'cl200k_base' else 'cl100k_base'
        encoding = tiktoken.get_encoding(encoding_name)

        # Helper function to extract text from content (handles multi-modal)
        def extract_text_from_content(content):
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Multi-modal content array - extract text from objects with type: "text"
                text = ''
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                        text += item['text']
                return text
            else:
                # Fallback: stringify the content
                return str(content)

        total_tokens = 0

        # Handle different input types
        if isinstance(input_data, str):
            # Simple string input
            total_tokens = len(encoding.encode(input_data))
        elif isinstance(input_data, list):
            # Array of messages
            for message in input_data:
                if isinstance(message, str):
                    total_tokens += len(encoding.encode(message))
                elif isinstance(message, dict) and 'content' in message:
                    # Message object with {role, content} - handle multi-modal content
                    text = extract_text_from_content(message['content'])
                    total_tokens += len(encoding.encode(text))
        elif isinstance(input_data, dict) and 'content' in input_data:
            # Single message object with {role, content} - handle multi-modal content
            text = extract_text_from_content(input_data['content'])
            total_tokens = len(encoding.encode(text))
        else:
            # Fallback: convert to string
            total_tokens = len(encoding.encode(str(input_data)))

        return {
            "tokens": total_tokens
        }

    except Exception as error:
        print(f'Token Count error: {error}')
        raise Exception(f"Token Count error: {str(error)}")
