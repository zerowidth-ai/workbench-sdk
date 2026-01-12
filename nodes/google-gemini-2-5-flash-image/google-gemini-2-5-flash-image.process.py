async def process({inputs, settings, config, nodeConfig}):
    """Process function for the Google: Gemini 2.5 Flash Image (Nano Banana) node"""
    try:
        # Get OpenRouter integration from engine
        openrouter = config.get("integrations", {}).get("openrouter")
        if not openrouter:
            raise Exception("OpenRouter integration not found")

        # No message processing needed for completion models

        # Build parameters dict from config inputs
        params = {}
        config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"modalities","display_name":"Modalities","type":"array","description":"Output modalities to request (e.g., [\"image\", \"text\"])","default":["image","text"]},{"name":"image_config","display_name":"Image Config","type":"object","description":"Image generation configuration (aspect_ratio: \"1:1\", \"16:9\", etc.)","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}]
        
        for input_def in config_inputs:
            value = inputs.get(input_def["name"])
            if value is not None:
                params[input_def["name"]] = value

        # Set default modalities for image generation if not provided
        if "modalities" not in params:
            params["modalities"] = ["image", "text"]

        response = await openrouter.chat_completion(
            model="google/gemini-2.5-flash-image",
            prompt=inputs.get("prompt"),
            **params,
            nodeConfig=nodeConfig,
            engineConfig=config
        )

        

        return {
            "content": response["content"],
            "images": response.get("images"),
            "finish_reason": response["finish_reason"],
            "usage": response["usage"]
            "cost_total": response.get("cost_total"),
            "cost_itemized": response.get("cost_itemized")
        }
    except Exception as e:
        raise Exception(f"Google: Gemini 2.5 Flash Image (Nano Banana) node error: {str(e)}")