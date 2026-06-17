export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        // Model is dynamic — read from input (or settings override), fall back to a default
        const model = inputs.model || settings?.model || "openai/text-embedding-3-small";

        if (inputs.input === null || inputs.input === undefined) {
            throw new Error("input is required");
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
            model: model,
            input: inputs.input,
            ...params
        }, nodeConfig, config);

        return {
            embedding: response.embedding,
            embeddings: response.embeddings,
            dimensions: response.dimensions,
            model: response.model,
            usage: response.usage,
            cost_total: response.cost_total ?? null,
            cost_itemized: response.cost_itemized ?? null
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`Embedding node error: ${error.message}`);
    }
};
