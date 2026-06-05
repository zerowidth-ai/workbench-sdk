export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        const documents = inputs.documents;
        if (!Array.isArray(documents)) {
            throw new Error("documents must be an array");
        }

        // Extract the text to rank for each document, preserving the original item
        const textField = inputs.text_field;
        const toText = (doc) => {
            if (typeof doc === 'string') return doc;
            if (doc && typeof doc === 'object') {
                if (textField && doc[textField] != null) return String(doc[textField]);
                for (const f of ['content', 'text', 'document', 'page_content', 'chunk', 'body']) {
                    if (doc[f] != null) return String(doc[f]);
                }
                return JSON.stringify(doc);
            }
            return String(doc);
        };
        const texts = documents.map(toText);

        const params = {};
        if (inputs.top_n !== null && inputs.top_n !== undefined) {
            params.top_n = inputs.top_n;
        }

        const response = await openrouter.rerank({
            model: "cohere/rerank-4-pro",
            query: inputs.query,
            documents: texts,
            ...params
        }, nodeConfig, config);

        // Reattach original documents by index, preserving the API's relevance order
        const results = (response.results || []).map(r => ({
            index: r.index,
            relevance_score: r.relevance_score,
            document: documents[r.index]
        }));

        return {
            results,
            ranked_documents: results.map(r => r.document),
            top_document: results.length > 0 ? results[0].document : null,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`Cohere: Rerank 4 Pro node error: ${error.message}`);
    }
};