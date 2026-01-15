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

        tokenizer = settings.get('tokenizer', 'cl200k_base')
        if tokenizer not in ['cl200k_base', 'cl100k_base']:
            raise Exception(f"Unsupported tokenizer: {tokenizer}. Only cl200k_base and cl100k_base are supported.")

        encoding_name = 'cl200k_base' if tokenizer == 'cl200k_base' else 'cl100k_base'
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

        # Start from the beginning and work forwards to find messages that fit
        result = []
        total_tokens = 0
        truncated = False

        for message in messages:
            message_tokens = count_message_tokens(message)
            
            if total_tokens + message_tokens <= max_tokens:
                result.append(message)
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
        print(f'Truncate by Tokens from Start error: {error}')
        raise Exception(f"Truncate by Tokens from Start error: {str(error)}")
