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
        const configInputs = [{"name":"prompt","display_name":"Prompt","type":"string","description":"Text prompt for completion","required":true},{"name":"modalities","display_name":"Modalities","type":"array","description":"Output modalities to request (e.g., [\"image\", \"text\"])","default":["image","text"]},{"name":"image_config","display_name":"Image Config","type":"object","description":"Image generation configuration (aspect_ratio: \"1:1\", \"16:9\", etc.)","default":null},{"name":"response_format","display_name":"Response Format","type":"string or object","description":"Output format specification","default":null},{"name":"seed","display_name":"Seed","type":"number","description":"Deterministic outputs","default":null},{"name":"temperature","display_name":"Temperature","type":"number","description":"Controls randomness (0-2)","default":null},{"name":"top_p","display_name":"Top P","type":"number","description":"Controls diversity via nucleus sampling","default":null}];
        
        for (const input of configInputs) {

            if(input.name === 'messages') continue;

            const value = inputs[input.name];
            if (value !== null && value !== undefined) {
                params[input.name] = value;
            }
        }

        // Set default modalities for image generation if not provided
        if (!params.modalities) {
            params.modalities = ["image", "text"];
        }

        const response = await openrouter.chatCompletion({
            model: "google/gemini-2.5-flash-image-preview",
            prompt: inputs.prompt,
            ...params
        }, nodeConfig, config);

        

        return {
            content: response.content,
            images: response.images,
            finish_reason: response.finish_reason,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`Google: Gemini 2.5 Flash Image Preview (Nano Banana) node error: ${error.message}`);
    }
};