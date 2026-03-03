export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        let messages = inputs.messages;

        if(typeof messages === 'string') {
            messages = [{ role: 'user', content: messages }];
        }

        if(typeof messages === 'object' && !Array.isArray(messages)) {
            messages = [messages];
        }

        if(inputs.system_prompt) {  
            let systemPrompt = inputs.system_prompt;
            if(typeof systemPrompt === 'string') {
                systemPrompt = { role: 'system', content: systemPrompt };
            }
            messages = [systemPrompt, ...messages];
        }

        // Build parameters object from config inputs
        const params = {};
        const configInputs = [{"name":"system_prompt","display_name":"System Prompt","type":"string or message","description":"System prompt to instruct the model","default":null},{"name":"messages","display_name":"Conversation","type":"conversation or message or string","description":"Array of chat messages that make up the conversation","required":true},{"name":"tools","display_name":"Tools","type":"tool or array of tools","description":"Array of tools to use","default":null,"allow_multiple":true},{"name":"frequency_penalty","display_name":"Frequency Penalty","type":"number","description":"Reduces repetition (-2 to 2)","default":null},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"presence_penalty","display_name":"Presence Penalty","type":"number","description":"Encourages new topics (-2 to 2)","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":null},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"tool_choice","display_name":"Tool Choice","type":"string","description":"Tool selection control","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}];
        
        for (const input of configInputs) {

            if(input.name === 'messages') continue;

            const value = inputs[input.name];
            if (value !== null && value !== undefined) {
                // Flatten tools array to handle both individual tools and arrays of tools
                if (input.name === 'tools' && Array.isArray(value)) {
                    params.tools = value.flat();
                } else {
                    params[input.name] = value;
                }
            }
        }

        

        const response = await openrouter.chatCompletion({
            model: "google/gemma-3-27b-it",
            messages: messages,
            ...params
        }, nodeConfig, config);

        // Get the set of internal tool names (tools handled by engine plugins)
        // If internal_tool_names is undefined, we're in backward-compatible mode (include all)
        // If it's an empty array, there are no internal tools (include none from history)
        const hasInternalToolTracking = config.internal_tool_names !== undefined;
        const internalToolNames = new Set(config.internal_tool_names || []);

        // Build conversation output: only include messages related to internal tools
        let conversationMessages = [];

        if (Array.isArray(messages) && messages.length > 0) {
            // Work backwards from the end
            for (let i = messages.length - 1; i >= 0; i--) {
                const msg = messages[i];
                if (!msg || typeof msg !== 'object') continue;

                const isTool = msg.role === 'tool';
                const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;

                if (isTool) {
                    // Only include tool result if it's for an internal tool
                    const toolName = msg.name;
                    if (!hasInternalToolTracking || internalToolNames.has(toolName)) {
                        conversationMessages.unshift(msg);
                    }
                    // Skip external tool results
                } else if (hasToolCalls) {
                    // Filter to only internal tool calls
                    const internalCalls = !hasInternalToolTracking
                        ? msg.tool_calls
                        : msg.tool_calls.filter(tc => internalToolNames.has(tc.function?.name));

                    if (internalCalls.length > 0) {
                        conversationMessages.unshift({
                            ...msg,
                            tool_calls: internalCalls
                        });
                    }
                    // External tool calls from history are dropped
                } else {
                    // Stop when we hit a message that is not tool and has no tool_calls
                    break;
                }
            }
        }

        // Append the final output message — always include all tool_calls on the response
        // The internal/external split only applies to historical messages above, not the fresh response
        const finalMessage = {
            content: response.content,
            role: response.role
        };

        if (response.tool_calls && Array.isArray(response.tool_calls) && response.tool_calls.length > 0) {
            finalMessage.tool_calls = response.tool_calls;
        }

        if (response.images) {
            finalMessage.images = response.images;
        }
        conversationMessages.push(finalMessage);

        const conversation = conversationMessages;

        return {
            conversation: conversation,
            message: {
                content: response.content,
                role: response.role,
                tool_calls: response.tool_calls
            },
            content: response.content,
            role: response.role,
            tool_calls: response.tool_calls,
            finish_reason: response.finish_reason,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`Google: Gemma 3 27B node error: ${error.message}`);
    }
};