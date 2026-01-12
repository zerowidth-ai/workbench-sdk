async def process({inputs, settings, config, nodeConfig}):
    """Process function for the OpenAI: GPT-4o-mini Search Preview node"""
    try:
        # Get OpenRouter integration from engine
        openrouter = config.get("integrations", {}).get("openrouter")
        if not openrouter:
            raise Exception("OpenRouter integration not found")

        # No message processing needed for completion models

        # Build parameters dict from config inputs
        params = {}
        config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null}]
        
        for input_def in config_inputs:
            value = inputs.get(input_def["name"])
            if value is not None:
                params[input_def["name"]] = value

        

        response = await openrouter.chat_completion(
            model="openai/gpt-4o-mini-search-preview",
            prompt=inputs.get("prompt"),
            **params,
            nodeConfig=nodeConfig,
            engineConfig=config
        )

        

        return {
            "content": response["content"],
            "annotations": response.get("annotations"),
            "citations": response.get("citations"),
            "finish_reason": response["finish_reason"],
            "usage": response["usage"]
            "cost_total": response.get("cost_total"),
            "cost_itemized": response.get("cost_itemized")
        }
    except Exception as e:
        raise Exception(f"OpenAI: GPT-4o-mini Search Preview node error: {str(e)}")