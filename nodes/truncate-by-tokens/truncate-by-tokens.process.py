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
        messages = inputs.get('messages')
        max_tokens = inputs.get('max_tokens')

        if not isinstance(messages, list):
            raise Exception("Messages input must be an array")

        if not isinstance(max_tokens, int) or max_tokens < 0:
            raise Exception("Max tokens must be a non-negative integer")

        tokenizer = settings.get('tokenizer', 'o200k_base')

        # Map tokenizer names (cl200k_base was a mistake, should be o200k_base)
        encoding_map = {
            'cl200k_base': 'o200k_base',  # Backwards compatibility
            'o200k_base': 'o200k_base',
            'cl100k_base': 'cl100k_base',
        }

        if tokenizer not in encoding_map:
            raise Exception(f"Unsupported tokenizer: {tokenizer}. Supported: o200k_base, cl100k_base")

        encoding_name = encoding_map[tokenizer]
        encoding = tiktoken.get_encoding(encoding_name)

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

        # Helper function to count tokens in a message
        def count_message_tokens(message):
            text = get_message_text(message)
            return len(encoding.encode(text))

        # Start from the end and work backwards to find messages that fit
        result = []
        total_tokens = 0
        truncated = False

        for i in range(len(messages) - 1, -1, -1):
            message = messages[i]
            message_tokens = count_message_tokens(message)
            
            if total_tokens + message_tokens <= max_tokens:
                result.insert(0, message)  # Add to beginning to maintain order
                total_tokens += message_tokens
            else:
                truncated = True
                break

        return {
            "messages": result,
            "token_count": total_tokens,
            "truncated": truncated
        }

    except Exception as error:
        print(f'Truncate by Tokens error: {error}')
        raise Exception(f"Truncate by Tokens error: {str(error)}")
