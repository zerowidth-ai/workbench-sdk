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
        tokens = inputs.get('tokens')
        if not isinstance(tokens, list):
            raise Exception("Tokens input must be an array of numbers")

        # Get the tokenizer setting, default to cl200k_base
        tokenizer = settings.get('tokenizer', 'cl200k_base')

        # Validate tokenizer option
        if tokenizer not in ['cl200k_base', 'cl100k_base']:
            raise Exception(f"Unsupported tokenizer: {tokenizer}. Only cl200k_base and cl100k_base are supported.")

        # Get the encoding for the specified tokenizer
        # Python tiktoken uses different names
        encoding_name = 'cl200k_base' if tokenizer == 'cl200k_base' else 'cl100k_base'
        encoding = tiktoken.get_encoding(encoding_name)

        # Convert to regular list if needed
        token_list = list(tokens) if not isinstance(tokens, list) else tokens

        # Validate that all tokens are numbers
        for i, token in enumerate(token_list):
            if not isinstance(token, int):
                raise Exception(f"Token at index {i} is not a valid integer: {token}")

        # Decode the tokens back to text
        decoded_bytes = encoding.decode(token_list)
        text = decoded_bytes if isinstance(decoded_bytes, str) else decoded_bytes.decode('utf-8')

        return {
            "text": text
        }

    except Exception as error:
        print(f'Untokenizer error: {error}')
        raise Exception(f"Untokenizer error: {str(error)}")
