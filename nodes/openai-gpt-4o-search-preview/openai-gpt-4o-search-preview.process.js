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
        const configInputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"max_tokens","display_name":"Max Tokens","type":"number","description":"Maximum tokens to generate","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null}];
        
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
            model: "openai/gpt-4o-search-preview",
            prompt: inputs.prompt,
            ...params
        }, nodeConfig, config);

        

        return {
            content: response.content,
            annotations: response.annotations,
            citations: response.citations,
            finish_reason: response.finish_reason,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`OpenAI: GPT-4o Search Preview node error: ${error.message}`);
    }
};