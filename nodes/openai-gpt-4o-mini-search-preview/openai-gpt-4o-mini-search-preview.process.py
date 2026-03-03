"""
OpenAI: GPT-4o-mini Search Preview - LLM node for the zv1 engine.
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
    Process function for the OpenAI: GPT-4o-mini Search Preview node.

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
    config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":True},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":None},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":None}]

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

    response = await openrouter.chat_completion(
        model="openai/gpt-4o-mini-search-preview",
        prompt=inputs.get("prompt"),
        **params,
        node_config=node_config,
        engine_config=config,
    )


    return {
        "content": response.get("content"),
        "annotations": response.get("annotations"),
        "citations": response.get("citations"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }