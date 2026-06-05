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
            model: "qwen/qwen3-embedding-4b",
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
        throw new Error(`Qwen: Qwen3 Embedding 4B node error: ${error.message}`);
    }
};