"""
Anthropic: Claude 3.5 Haiku - LLM node for the zv1 engine.
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
    Process function for the Anthropic: Claude 3.5 Haiku node.

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

    messages = inputs.get("messages", [])

    # Handle string input - convert to user message
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    # Handle single message object - wrap in list
    if isinstance(messages, dict):
        messages = [messages]

    # Prepend system prompt if provided
    if inputs.get("system_prompt"):
        system_prompt = inputs.get("system_prompt")
        if isinstance(system_prompt, str):
            system_prompt = {"role": "system", "content": system_prompt}
        messages = [system_prompt, *messages]

    # Build parameters dict from config inputs
    params = {}
    config_inputs = [{"name":"system_prompt","display_name":"System Prompt","type":"string or message","description":"System prompt to instruct the model","default":None},{"name":"messages","display_name":"Conversation","type":"conversation or message or string","description":"Array of chat messages that make up the conversation","required":True},{"name":"tools","display_name":"Tools","type":"tool","description":"Array of tools to use","default":None,"allow_multiple":True},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":None},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":None},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":None},{"name":"tool_choice","display_name":"Tool Choice","type":"string","description":"Tool selection control","default":None},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":None}]

    for input_def in config_inputs:
        if input_def["name"] == "messages":
            continue
        value = inputs.get(input_def["name"])
        if value is not None:
            params[input_def["name"]] = value

    response = await openrouter.chat_completion(
        model="anthropic/claude-3.5-haiku",
        messages=messages,
        **params,
        node_config=node_config,
        engine_config=config,
    )

    # Build conversation output: collect tool-related messages from end of input
    conversation_messages: list[dict[str, Any]] = []
    if isinstance(messages, list) and len(messages) > 0:
        # Work backwards from the end
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not isinstance(msg, dict):
                continue

            is_tool = msg.get("role") == "tool"
            tool_calls = msg.get("tool_calls")
            has_tool_calls = (
                tool_calls is not None
                and isinstance(tool_calls, list)
                and len(tool_calls) > 0
            )

            # Include this message if it's a tool message or has tool_calls
            if is_tool or has_tool_calls:
                conversation_messages.insert(0, msg)
            else:
                # Stop when we hit a message that is not tool and has no tool_calls
                break

    # Append the final output message
    final_message: dict[str, Any] = {
        "content": response.get("content"),
        "role": response.get("role"),
    }
    if response.get("tool_calls"):
        final_message["tool_calls"] = response.get("tool_calls")
    if response.get("images"):
        final_message["images"] = response.get("images")
    conversation_messages.append(final_message)

    conversation = conversation_messages
    return {
        "conversation": conversation,
        "message": {
            "content": response.get("content"),
            "role": response.get("role"),
            "tool_calls": response.get("tool_calls"),
        },
        "content": response.get("content"),
        "role": response.get("role"),
        "tool_calls": response.get("tool_calls"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }