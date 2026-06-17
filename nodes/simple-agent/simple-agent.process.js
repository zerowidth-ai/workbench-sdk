export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        // Model is dynamic — read from input (or settings override), fall back to a default
        const model = inputs.model || settings?.model || "openai/gpt-4.1-nano";

        let messages = inputs.messages;

        if (typeof messages === 'string') {
            messages = [{ role: 'user', content: messages }];
        }

        if (typeof messages === 'object' && !Array.isArray(messages)) {
            messages = [messages];
        }

        if (inputs.system_prompt) {
            let systemPrompt = inputs.system_prompt;
            if (typeof systemPrompt === 'string') {
                systemPrompt = { role: 'system', content: systemPrompt };
            }
            messages = [systemPrompt, ...messages];
        }

        // Build parameters from the remaining inputs (skip the ones handled explicitly)
        const params = {};
        const passthrough = ['tools', 'tool_choice', 'temperature', 'max_tokens'];
        for (const name of passthrough) {
            const value = inputs[name];
            if (value !== null && value !== undefined) {
                // Flatten tools to handle both individual tools and arrays of tools
                if (name === 'tools' && Array.isArray(value)) {
                    params.tools = value.flat();
                } else {
                    params[name] = value;
                }
            }
        }

        const response = await openrouter.chatCompletion({
            model: model,
            messages: messages,
            ...params
        }, nodeConfig, config);

        // Build conversation output: only include history messages tied to internal
        // (engine-executed) tools; external/manual tool calls from history are dropped.
        const hasInternalToolTracking = config.internal_tool_names !== undefined;
        const internalToolNames = new Set(config.internal_tool_names || []);

        let conversationMessages = [];

        if (Array.isArray(messages) && messages.length > 0) {
            for (let i = messages.length - 1; i >= 0; i--) {
                const msg = messages[i];
                if (!msg || typeof msg !== 'object') continue;

                const isTool = msg.role === 'tool';
                const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;

                if (isTool) {
                    const toolName = msg.name;
                    if (!hasInternalToolTracking || internalToolNames.has(toolName)) {
                        conversationMessages.unshift(msg);
                    }
                } else if (hasToolCalls) {
                    const internalCalls = !hasInternalToolTracking
                        ? msg.tool_calls
                        : msg.tool_calls.filter(tc => internalToolNames.has(tc.function?.name));

                    if (internalCalls.length > 0) {
                        conversationMessages.unshift({
                            ...msg,
                            tool_calls: internalCalls
                        });
                    }
                } else {
                    break;
                }
            }
        }

        // Append the final output message — always include all tool_calls on the response
        const finalMessage = {
            content: response.content,
            role: response.role
        };

        if (response.tool_calls && Array.isArray(response.tool_calls) && response.tool_calls.length > 0) {
            finalMessage.tool_calls = response.tool_calls;
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
            cost_total: response.cost_total ?? null,
            cost_itemized: response.cost_itemized ?? null
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`Simple Agent node error: ${error.message}`);
    }
};
