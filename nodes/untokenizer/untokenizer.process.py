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
