"""
OpenAI: o1-pro - LLM node for the zv1 engine.
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
    Process function for the OpenAI: o1-pro node.

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
    config_inputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":True},{"name":"include_reasoning","display_name":"Include Reasoning","type":"boolean","description":"Include reasoning in response","default":None},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":None},{"name":"reasoning","display_name":"Reasoning","type":"boolean","description":"Internal reasoning mode","default":None},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":None},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":None}]

    for input_def in config_inputs:
        if input_def["name"] == "messages":
            continue
        value = inputs.get(input_def["name"])
        if value is not None:
            params[input_def["name"]] = value

    response = await openrouter.chat_completion(
        model="openai/o1-pro",
        prompt=inputs.get("prompt"),
        **params,
        node_config=node_config,
        engine_config=config,
    )


    return {
        "content": response.get("content"),
        "reasoning": response.get("reasoning"),
        "refusal": response.get("refusal"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }