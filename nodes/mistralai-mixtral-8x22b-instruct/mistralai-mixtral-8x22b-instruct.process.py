async def process({inputs, settings, config, nodeConfig}):
    """Process function for the Mistral: Mixtral 8x22B Instruct node"""
    try:
        # Get OpenRouter integration from engine
        openrouter = config.get("integrations", {}).get("openrouter")
        if not openrouter:
            raise Exception("OpenRouter integration not found")

        messages = inputs.get("messages", [])

        if isinstance(messages, str):
            messages = [{ "role": "user", "content": messages }]

        if isinstance(messages, dict):
            messages = [messages]

        if inputs.get("system_prompt"):
            system_prompt = inputs.get("system_prompt") 
            if isinstance(system_prompt, str):
                system_prompt = {"role": "system", "content": system_prompt}

            messages = [system_prompt, *messages]

        # Build parameters dict from config inputs
        params = {}
        config_inputs = [{"name":"system_prompt","display_name":"System Prompt","type":"string or message","description":"System prompt to instruct the model","default":null},{"name":"messages","display_name":"Conversation","type":"conversation or message or string","description":"Array of chat messages that make up the conversation","required":true},{"name":"tools","display_name":"Tools","type":"tool","description":"Array of tools to use","default":null,"allow_multiple":true},{"name":"frequency_penalty","display_name":"Frequency Penalty","type":"number","description":"Reduces repetition (-2 to 2)","default":null},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"presence_penalty","display_name":"Presence Penalty","type":"number","description":"Encourages new topics (-2 to 2)","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":null},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"tool_choice","display_name":"Tool Choice","type":"string","description":"Tool selection control","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}]
        
        for input_def in config_inputs:
            value = inputs.get(input_def["name"])
            if value is not None:
                params[input_def["name"]] = value

        

        response = await openrouter.chat_completion(
            model="mistralai/mixtral-8x22b-instruct",
            messages=messages,
            **params,
            nodeConfig=nodeConfig,
            engineConfig=config
        )

        # Build conversation output: slice from end of input messages until we hit a non-tool message without tool_calls
        conversation_messages = []
        if isinstance(messages, list) and len(messages) > 0:
            # Work backwards from the end
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if not isinstance(msg, dict):
                    continue
                
                is_tool = msg.get("role") == "tool"
                has_tool_calls = msg.get("tool_calls") and isinstance(msg.get("tool_calls"), list) and len(msg.get("tool_calls", [])) > 0
                
                # Include this message if it's a tool message or has tool_calls
                if is_tool or has_tool_calls:
                    conversation_messages.insert(0, msg)
                else:
                    # Stop when we hit a message that is not tool and has no tool_calls
                    # Include this message as the starting point
                    conversation_messages.insert(0, msg)
                    break
        
        # Append the final output message
        final_message = {
            "content": response.get("content"),
            "role": response.get("role")
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
                "content": response["content"],
                "role": response["role"],
                "tool_calls": response.get("tool_calls")
            },
            "content": response["content"],
            "role": response["role"],
            "tool_calls": response.get("tool_calls"),
            "finish_reason": response["finish_reason"],
            "usage": response["usage"]
            "cost_total": response.get("cost_total"),
            "cost_itemized": response.get("cost_itemized")
        }
    except Exception as e:
        raise Exception(f"Mistral: Mixtral 8x22B Instruct node error: {str(e)}")