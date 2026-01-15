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

        count_system = settings.get('count_system', False)  # Default to False

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

        # Separate system and non-system messages
        system_messages = []
        non_system_messages = []

        for message in messages:
            if isinstance(message, dict) and message.get('role') == 'system':
                system_messages.append(message)
            else:
                non_system_messages.append(message)

        # Count tokens in system messages
        system_tokens = 0
        for message in system_messages:
            system_tokens += count_message_tokens(message)

        # Handle system messages based on count_system setting
        result = []
        total_tokens = 0
        truncated = False

        if max_tokens == 0:
            # Zero token limit - don't include any messages
            truncated = len(system_messages) > 0 or len(non_system_messages) > 0
        elif count_system:
            # System messages count toward limit - only include if they fit
            if system_tokens <= max_tokens:
                result.extend(system_messages)
                total_tokens = system_tokens
            else:
                # System messages exceed limit - don't include them
                truncated = len(system_messages) > 0
        else:
            # System messages don't count toward limit - always include them
            result.extend(system_messages)
            total_tokens = system_tokens
            if system_tokens > max_tokens:
                truncated = True

        # Only process non-system messages if we have room and token limit > 0
        if max_tokens > 0 and (system_tokens <= max_tokens or not count_system):
            for i in range(len(non_system_messages) - 1, -1, -1):
                message = non_system_messages[i]
                message_tokens = count_message_tokens(message)
                
                if total_tokens + message_tokens <= max_tokens:
                    result.append(message)
                    total_tokens += message_tokens
                else:
                    truncated = True
                    break
        elif max_tokens > 0 and system_tokens > max_tokens and count_system:
            # System messages exceed limit and count_system is true, so non-system messages are truncated
            truncated = len(non_system_messages) > 0

        # Sort result to maintain original order (system messages first, then others)
        result.sort(key=lambda x: messages.index(x) if x in messages else 0)

        # Count system messages in the result
        result_system_count = len([msg for msg in result if isinstance(msg, dict) and msg.get('role') == 'system'])

        return {
            "messages": result,
            "token_count": total_tokens,
            "truncated": truncated,
            "system_count": result_system_count
        }

    except Exception as error:
        print(f'Truncate by Tokens Preserve System error: {error}')
        raise Exception(f"Truncate by Tokens Preserve System error: {str(error)}")
