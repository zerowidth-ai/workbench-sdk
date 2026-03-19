export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        // No message processing needed for completion models

        // Build parameters object from config inputs
        const params = {};
        const configInputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"reasoning","display_name":"Reasoning","type":"boolean","description":"Enable reasoning mode","default":null},{"name":"response_format","display_name":"Response Format","type":"object","description":"Output format specification","default":null},{"name":"stop","display_name":"Stop","type":"string or array","description":"Custom stop sequences","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"frequency_penalty","display_name":"Frequency Penalty","type":"number","description":"Reduces repetition (-2 to 2)","default":null},{"name":"presence_penalty","display_name":"Presence Penalty","type":"number","description":"Encourages new topics (-2 to 2)","default":null},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":null}];
        
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
            model: "deepseek/deepseek-v3.2-speciale",
            prompt: inputs.prompt,
            ...params
        }, nodeConfig, config);

        

        return {
            content: response.content,
            reasoning: response.reasoning,
            refusal: response.refusal,
            finish_reason: response.finish_reason,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`DeepSeek: DeepSeek V3.2 Speciale node error: ${error.message}`);
    }
};