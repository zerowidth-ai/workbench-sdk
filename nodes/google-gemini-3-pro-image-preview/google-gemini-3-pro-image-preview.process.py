"""
Google: Nano Banana Pro (Gemini 3 Pro Image Preview) - LLM node for the zv1 engine.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Google: Nano Banana Pro (Gemini 3 Pro Image Preview) node.

    Args:
        inputs: Node inputs containing messages/prompt and parameters.
        settings: Node settings (unused for LLM nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with conversation, message, content, and usage data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    # Completion model - no message processing needed
    pass

    # Build parameters dict from config inputs
    params = {}
    config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":True},{"name":"modalities","display_name":"Modalities","type":"array","description":"Output modalities to request (e.g., [\"image\", \"text\"])","default":["image","text"]},{"name":"image_config","display_name":"Image Config","type":"object","description":"Image generation configuration (aspect_ratio: \"1:1\", \"16:9\", etc.)","default":None},{"name":"reasoning","display_name":"Reasoning","type":"boolean","description":"Enable reasoning mode","default":None},{"name":"response_format","display_name":"Response Format","type":"object","description":"Output format specification","default":None},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":None},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":None},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":None}]

    for input_def in config_inputs:
        if input_def["name"] == "messages":
            continue
        value = inputs.get(input_def["name"])
        if value is not None:
            # Flatten tools array to handle both individual tools and arrays of tools
            if input_def["name"] == "tools" and isinstance(value, list):
                flat_tools = []
                for item in value:
                    if isinstance(item, list):
                        flat_tools.extend(item)
                    else:
                        flat_tools.append(item)
                params["tools"] = flat_tools
            else:
                params[input_def["name"]] = value

    # Set default modalities for image generation if not provided
    if "modalities" not in params:
        params["modalities"] = ["image", "text"]

    response = await openrouter.chat_completion(
        model="google/gemini-3-pro-image-preview",
        prompt=inputs.get("prompt"),
        **params,
        node_config=node_config,
        engine_config=config,
    )


    return {
        "content": response.get("content"),
        "images": response.get("images"),
        "reasoning": response.get("reasoning"),
        "refusal": response.get("refusal"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }