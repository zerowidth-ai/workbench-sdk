async def process({inputs, settings, config, nodeConfig}):
    """Process function for the DeepSeek: DeepSeek V3.2 Speciale node"""
    try:
        # Get OpenRouter integration from engine
        openrouter = config.get("integrations", {}).get("openrouter")
        if not openrouter:
            raise Exception("OpenRouter integration not found")

        # No message processing needed for completion models

        # Build parameters dict from config inputs
        params = {}
        config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"frequency_penalty","display_name":"Frequency Penalty","type":"number","description":"Reduces repetition (-2 to 2)","default":null},{"name":"include_reasoning","display_name":"Include Reasoning","type":"boolean","description":"Include reasoning in response","default":null},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"presence_penalty","display_name":"Presence Penalty","type":"number","description":"Encourages new topics (-2 to 2)","default":null},{"name":"reasoning","display_name":"Reasoning","type":"boolean","description":"Internal reasoning mode","default":null},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}]
        
        for input_def in config_inputs:
            value = inputs.get(input_def["name"])
            if value is not None:
                params[input_def["name"]] = value

        

        response = await openrouter.chat_completion(
            model="deepseek/deepseek-v3.2-speciale",
            prompt=inputs.get("prompt"),
            **params,
            nodeConfig=nodeConfig,
            engineConfig=config
        )

        

        return {
            "content": response["content"],
            "reasoning": response.get("reasoning"),
            "refusal": response.get("refusal"),
            "logprobs": response.get("logprobs"),
            "finish_reason": response["finish_reason"],
            "usage": response["usage"]
            "cost_total": response.get("cost_total"),
            "cost_itemized": response.get("cost_itemized")
        }
    except Exception as e:
        raise Exception(f"DeepSeek: DeepSeek V3.2 Speciale node error: {str(e)}")