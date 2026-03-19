"""
OpenAI: GPT-3.5 Turbo - LLM node for the zv1 engine.
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
    Process function for the OpenAI: GPT-3.5 Turbo node.

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
    config_inputs = [{"name":"messages","display_name":"Conversation","type":"conversation or message or string","description":"Array of chat messages that make up the conversation","required":True},{"name":"system_prompt","display_name":"System Message","type":"message or string","description":"System prompt to instruct the model","default":None},{"name":"tools","display_name":"Tools","type":"tool or array of tools","description":"Array of tools to use","default":None,"allow_multiple":True},{"name":"tool_choice","display_name":"Tool Choice","type":"string","description":"Tool selection control","default":None},{"name":"response_format","display_name":"Response Format","type":"object","description":"Output format specification","default":None},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":None},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":None},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":None},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":None},{"name":"frequency_penalty","display_name":"Frequency Penalty","type":"number","description":"Reduces repetition (-2 to 2)","default":None},{"name":"presence_penalty","display_name":"Presence Penalty","type":"number","description":"Encourages new topics (-2 to 2)","default":None},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":None}]

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
        model="openai/gpt-3.5-turbo",
        messages=messages,
        **params,
        node_config=node_config,
        engine_config=config,
    )

    # Get the set of internal tool names (tools handled by engine plugins)
    # If internal_tool_names is not in config, we're in backward-compatible mode (include all)
    # If it's an empty list, there are no internal tools (include none from history)
    has_internal_tool_tracking = "internal_tool_names" in config
    internal_tool_names: set[str] = set(config.get("internal_tool_names", []))

    # Build conversation output: only include messages related to internal tools
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

            if is_tool:
                # Only include tool result if it's for an internal tool
                tool_name = msg.get("name")
                if not has_internal_tool_tracking or tool_name in internal_tool_names:
                    conversation_messages.insert(0, msg)
                # Skip external tool results
            elif has_tool_calls:
                # Filter to only internal tool calls
                if not has_internal_tool_tracking:
                    internal_calls = tool_calls
                else:
                    internal_calls = [
                        tc for tc in tool_calls
                        if tc.get("function", {}).get("name") in internal_tool_names
                    ]

                if len(internal_calls) > 0:
                    filtered_msg = {**msg, "tool_calls": internal_calls}
                    conversation_messages.insert(0, filtered_msg)
                # External tool calls from history are dropped
            else:
                # Stop when we hit a message that is not tool and has no tool_calls
                break

    # Append the final output message — always include all tool_calls on the response
    # The internal/external split only applies to historical messages above, not the fresh response
    final_message: dict[str, Any] = {
        "content": response.get("content"),
        "role": response.get("role"),
    }

    response_tool_calls = response.get("tool_calls")
    if (
        response_tool_calls is not None
        and isinstance(response_tool_calls, list)
        and len(response_tool_calls) > 0
    ):
        final_message["tool_calls"] = response_tool_calls

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
        "logprobs": response.get("logprobs"),
        "finish_reason": response.get("finish_reason"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }