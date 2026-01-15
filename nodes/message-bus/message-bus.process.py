from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        preserve_order = settings.get('preserve_order', True)
        filter_empty = settings.get('filter_empty', True)

        # Helper function to extract messages from input
        def extract_messages(input_data):
            if not input_data:
                return []
            
            if isinstance(input_data, list):
                return input_data
            elif isinstance(input_data, dict) and 'role' in input_data:
                return [input_data]
            elif isinstance(input_data, str):
                # Convert string to user message
                return [{
                    'role': 'user',
                    'content': input_data
                }]
            else:
                return []

        # Helper function to filter empty messages
        def filter_messages(messages):
            if not filter_empty:
                return messages
            
            filtered = []
            for message in messages:
                if not message:
                    continue
                if not isinstance(message, dict):
                    continue
                if 'role' not in message:
                    continue
                if message.get('content') is None:
                    continue
                if isinstance(message.get('content'), str) and message.get('content').strip() == '':
                    continue
                if isinstance(message.get('content'), list) and len(message.get('content')) == 0:
                    continue
                filtered.append(message)
            return filtered

        all_messages = []
        inputs_used = 0

        # Process inputs in order (input_1 through input_8)
        input_keys = ['input_1', 'input_2', 'input_3', 'input_4', 'input_5', 'input_6', 'input_7', 'input_8']
        
        for input_key in input_keys:
            input_data = inputs.get(input_key)
            messages = extract_messages(input_data)
            
            if len(messages) > 0:
                filtered_messages = filter_messages(messages)
                if len(filtered_messages) > 0:
                    all_messages.extend(filtered_messages)
                    inputs_used += 1

        return {
            "messages": all_messages,
            "message_count": len(all_messages),
            "inputs_used": inputs_used
        }

    except Exception as error:
        print(f'Message Bus error: {error}')
        raise Exception(f"Message Bus error: {str(error)}")
