"""
Simple Agent - configurable agent node for the zv1 engine.

The model is an input, so the chat model can be specified or swapped from
outside the flow. The engine runs the tool-calling loop around this node
(via accepts_plugins), so attached plugins/tools are handled automatically.
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
    Process function for the Simple Agent node.

    Args:
        inputs: Node inputs containing messages, model, system_prompt and params.
        settings: Node settings (optional model override).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with conversation, message, content, usage and cost data.
    """
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    # Model is dynamic — read from input (or settings override), fall back to a default
    model = inputs.get("model") or (settings or {}).get("model") or "openai/gpt-4.1-nano"

    messages = inputs.get("messages", [])

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    if isinstance(messages, dict):
        messages = [messages]

    if inputs.get("system_prompt"):
        system_prompt = inputs.get("system_prompt")
        if isinstance(system_prompt, str):
            system_prompt = {"role": "system", "content": system_prompt}
        messages = [system_prompt, *messages]

    # Build params from the remaining inputs (skip ones handled explicitly)
    params: dict[str, Any] = {}
    for name in ("tools", "tool_choice", "temperature", "max_tokens"):
        value = inputs.get(name)
        if value is not None:
            if name == "tools" and isinstance(value, list):
                flat_tools = []
                for item in value:
                    if isinstance(item, list):
                        flat_tools.extend(item)
                    else:
                        flat_tools.append(item)
                params["tools"] = flat_tools
            else:
                params[name] = value

    response = await openrouter.chat_completion(
        model=model,
        messages=messages,
        **params,
        node_config=node_config,
        engine_config=config,
    )

    # Build conversation output: only include history messages tied to internal
    # (engine-executed) tools; external/manual tool calls from history are dropped.
    has_internal_tool_tracking = "internal_tool_names" in config
    internal_tool_names: set[str] = set(config.get("internal_tool_names", []))

    conversation_messages: list[dict[str, Any]] = []

    if isinstance(messages, list) and len(messages) > 0:
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
                tool_name = msg.get("name")
                if not has_internal_tool_tracking or tool_name in internal_tool_names:
                    conversation_messages.insert(0, msg)
            elif has_tool_calls:
                if not has_internal_tool_tracking:
                    internal_calls = tool_calls
                else:
                    internal_calls = [
                        tc for tc in tool_calls
                        if tc.get("function", {}).get("name") in internal_tool_names
                    ]

                if len(internal_calls) > 0:
                    conversation_messages.insert(0, {**msg, "tool_calls": internal_calls})
            else:
                break

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

    conversation_messages.append(final_message)

    return {
        "conversation": conversation_messages,
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
