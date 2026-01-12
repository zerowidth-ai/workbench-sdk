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
        const configInputs = [{"name":"system_prompt","display_name":"System Prompt","type":"string or message","description":"System prompt to instruct the model","default":null},{"name":"messages","display_name":"Conversation","type":"conversation or message or string","description":"Array of chat messages that make up the conversation","required":true},{"name":"tools","display_name":"Tools","type":"tool","description":"Array of tools to use","default":null,"allow_multiple":true},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"tool_choice","display_name":"Tool Choice","type":"string","description":"Tool selection control","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}];
        
        for (const input of configInputs) {

            if(input.name === 'messages') continue;

            const value = inputs[input.name];
            if (value !== null && value !== undefined) {
                params[input.name] = value;
            }
        }

        

        const response = await openrouter.chatCompletion({
            model: "anthropic/claude-3.5-haiku",
            messages: messages,
            ...params
        }, nodeConfig, config);

        // Build conversation output: slice from end of input messages until we hit a non-tool message without tool_calls
        let conversationMessages = [];
        if (Array.isArray(messages) && messages.length > 0) {
            // Work backwards from the end
            for (let i = messages.length - 1; i >= 0; i--) {
                const msg = messages[i];
                if (!msg || typeof msg !== 'object') continue;
                
                const isTool = msg.role === 'tool';
                const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;
                
                // Include this message if it's a tool message or has tool_calls
                if (isTool || hasToolCalls) {
                    conversationMessages.unshift(msg);
                } else {
                    // Stop when we hit a message that is not tool and has no tool_calls
                    break;
                }
            }
        }
        
        // Append the final output message
        const finalMessage = {
            content: response.content,
            role: response.role
        };
        if (response.tool_calls) {
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
        throw new Error(`Anthropic: Claude 3.5 Haiku node error: ${error.message}`);
    }
};