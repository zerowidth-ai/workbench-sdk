import asyncio
import aiohttp
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
            raise Exception("Input is required for moderation")

        # Extract content from Message object or use input directly
        moderation_input = input_data
        
        # Handle Message object with {role, content} structure
        if (input_data and isinstance(input_data, dict) and 
            not isinstance(input_data, list) and 'content' in input_data):
            moderation_input = input_data['content']
        
        # If it's a string, use it directly
        # If it's a list, use it as-is (should be multi-modal format)
        if isinstance(moderation_input, str):
            moderation_input = moderation_input
        elif isinstance(moderation_input, list):
            moderation_input = moderation_input
        else:
            # Convert single object to list
            moderation_input = [moderation_input]

        # Get API key from config
        api_key = config.get('keys', {}).get('openai')
        if not api_key:
            raise Exception("OpenAI API key not found in config.keys.openai")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/moderations',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                },
                json={
                    'model': 'omni-moderation-latest',
                    'input': moderation_input
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status >= 400:
                    error_data = await response.json()
                    error_msg = error_data.get('error', {}).get('message', response.reason)
                    raise Exception(f"OpenAI API error: {response.status} - {error_msg}")
                
                response_data = await response.json()

        # Extract the first result (API returns list of results)
        result = response_data.get('results', [{}])[0] if response_data.get('results') else {}
        categories = result.get('categories', {})
        category_scores = result.get('category_scores', {})

        return {
            "flagged": result.get('flagged', False),
            "sexual": categories.get('sexual', False),
            "sexual_score": category_scores.get('sexual', 0),
            "sexual_minors": categories.get('sexual/minors', False),
            "sexual_minors_score": category_scores.get('sexual/minors', 0),
            "harassment": categories.get('harassment', False),
            "harassment_score": category_scores.get('harassment', 0),
            "harassment_threatening": categories.get('harassment/threatening', False),
            "harassment_threatening_score": category_scores.get('harassment/threatening', 0),
            "hate": categories.get('hate', False),
            "hate_score": category_scores.get('hate', 0),
            "hate_threatening": categories.get('hate/threatening', False),
            "hate_threatening_score": category_scores.get('hate/threatening', 0),
            "illicit": categories.get('illicit', False),
            "illicit_score": category_scores.get('illicit', 0),
            "illicit_violent": categories.get('illicit/violent', False),
            "illicit_violent_score": category_scores.get('illicit/violent', 0),
            "self_harm": categories.get('self-harm', False),
            "self_harm_score": category_scores.get('self-harm', 0),
            "self_harm_intent": categories.get('self-harm/intent', False),
            "self_harm_intent_score": category_scores.get('self-harm/intent', 0),
            "self_harm_instructions": categories.get('self-harm/instructions', False),
            "self_harm_instructions_score": category_scores.get('self-harm/instructions', 0),
            "violence": categories.get('violence', False),
            "violence_score": category_scores.get('violence', 0),
            "violence_graphic": categories.get('violence/graphic', False),
            "violence_graphic_score": category_scores.get('violence/graphic', 0)
        }

    except Exception as error:
        print(f'OpenAI Omni Moderation error: {error}')
        raise Exception(f"OpenAI Omni Moderation error: {str(error)}")
