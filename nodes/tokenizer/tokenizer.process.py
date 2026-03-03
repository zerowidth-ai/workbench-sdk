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
        if input_data is None:
            raise Exception("Input is required for tokenization")

        # Get the tokenizer setting, default to o200k_base (GPT-4o tokenizer)
        tokenizer = settings.get('tokenizer', 'o200k_base')

        # Map tokenizer names (cl200k_base was a mistake, should be o200k_base)
        encoding_map = {
            'cl200k_base': 'o200k_base',  # Backwards compatibility
            'o200k_base': 'o200k_base',
            'cl100k_base': 'cl100k_base',
        }

        # Validate and map tokenizer option
        if tokenizer not in encoding_map:
            raise Exception(f"Unsupported tokenizer: {tokenizer}. Supported: o200k_base, cl100k_base")

        encoding_name = encoding_map[tokenizer]
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

        all_tokens = []

        # Handle different input types
        if isinstance(input_data, str):
            # Simple string input
            all_tokens = encoding.encode(input_data)
        elif isinstance(input_data, list):
            # Array of messages
            for message in input_data:
                if isinstance(message, str):
                    all_tokens.extend(encoding.encode(message))
                elif isinstance(message, dict) and 'content' in message:
                    # Message object with {role, content} - handle multi-modal content
                    text = extract_text_from_content(message['content'])
                    all_tokens.extend(encoding.encode(text))
        elif isinstance(input_data, dict) and 'content' in input_data:
            # Single message object with {role, content} - handle multi-modal content
            text = extract_text_from_content(input_data['content'])
            all_tokens = encoding.encode(text)
        else:
            # Fallback: convert to string
            all_tokens = encoding.encode(str(input_data))

        return {
            "tokens": all_tokens
        }

    except Exception as error:
        print(f'Tokenizer error: {error}')
        raise Exception(f"Tokenizer error: {str(error)}")
