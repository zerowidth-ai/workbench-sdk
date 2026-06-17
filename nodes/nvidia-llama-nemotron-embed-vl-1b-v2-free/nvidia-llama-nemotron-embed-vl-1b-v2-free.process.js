export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        // Build optional parameters (only sent when provided)
        const params = {};
        if (inputs.dimensions !== null && inputs.dimensions !== undefined) {
            params.dimensions = inputs.dimensions;
        }
        if (inputs.encoding_format !== null && inputs.encoding_format !== undefined) {
            params.encoding_format = inputs.encoding_format;
        }

        const response = await openrouter.createEmbedding({
            model: "nvidia/llama-nemotron-embed-vl-1b-v2:free",
            input: inputs.input,
            ...params
        }, nodeConfig, config);

        return {
            embedding: response.embedding,
            embeddings: response.embeddings,
            dimensions: response.dimensions,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`NVIDIA: Llama Nemotron Embed VL 1B V2 (free) node error: ${error.message}`);
    }
};