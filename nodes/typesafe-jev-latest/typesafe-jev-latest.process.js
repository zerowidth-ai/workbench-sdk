export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        const response = await openrouter.systemOne({
            model: "~typesafe/jev-latest",
            state: inputs.state,
            questions: inputs.questions
        }, nodeConfig, config);

        // Primary value per answer type, for easy wiring downstream
        const values = {};
        for (const [id, answer] of Object.entries(response.answers || {})) {
            values[id] = answer?.[answer?.type] ?? null;
        }

        return {
            answers: response.answers,
            values,
            model: response.model,
            usage: response.usage,
            cost_total: response.cost_total,
            cost_itemized: response.cost_itemized
        };
    } catch (error) {
        console.log('error', error);
        throw new Error(`TypeSafe: Jev Latest node error: ${error.message}`);
    }
};