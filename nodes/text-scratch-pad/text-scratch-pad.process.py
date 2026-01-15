from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        text = inputs.get('text')
        delimiter = inputs.get('delimiter') or settings.get('default_delimiter', '\n')
        clear = inputs.get('clear', False)
        
        # Get current accumulated content from settings
        current_content = settings.get('accumulated_content') or settings.get('initial_content', '')
        
        # Clear if requested
        if clear:
            current_content = ''
        
        # Add new text if provided
        if text is not None and text != '':
            if current_content == '':
                # First addition, no delimiter needed
                current_content = str(text)
            else:
                # Subsequent additions, use delimiter
                current_content = current_content + delimiter + str(text)
        
        # Update settings to persist the accumulated content
        outputs = {
            'content': current_content,
            'length': len(current_content),
            '__updated_settings': {
                'accumulated_content': current_content
            }
        }
        
        return outputs
        
    except Exception as error:
        raise Exception(f"Text Scratch Pad error: {str(error)}")
