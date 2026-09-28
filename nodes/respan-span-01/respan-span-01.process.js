// This model scores a conversation span: { input: [messages], output: assistantMessage },
// where every message has string content. Convert workbench conversation/message
// shapes into that; plain strings pass through; other data is sent as JSON text.
const SPAN_ROLES = { system: 'system', developer: 'system', user: 'user', assistant: 'assistant', tool: 'tool' };
const contentToText = (content) => {
    if (content === null || content === undefined) return '';
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
        return content
            .map(part => typeof part === 'string' ? part : (part?.text ?? (part?.type === 'image_url' ? '[image]' : JSON.stringify(part))))
            .join('\n');
    }
    return JSON.stringify(content);
};
const isMessage = (m) => m !== null && typeof m === 'object' && !Array.isArray(m) && typeof m.role === 'string';
const toSpanMessage = (m) => {
    const text = contentToText(m.content);
    return {
        role: SPAN_ROLES[m.role] || 'user',
        content: text || (m.tool_calls ? JSON.stringify(m.tool_calls) : '')
    };
};
const toSpanState = (state) => {
    if (typeof state === 'string') return state;
    if (isMessage(state) || (Array.isArray(state) && state.length > 0 && state.every(isMessage))) {
        const messages = Array.isArray(state) ? state : [state];
        const last = messages[messages.length - 1];
        if (last.role !== 'assistant') {
            throw new Error(`this model scores a conversation span that ends with an assistant reply, but the last message has role "${last.role}". Connect a conversation ending in an assistant message, or a string.`);
        }
        return { input: messages.slice(0, -1).map(toSpanMessage), output: toSpanMessage(last) };
    }
    if (state !== null && typeof state === 'object' && !Array.isArray(state) && Array.isArray(state.input) && isMessage(state.output)) {
        return state; // already a span
    }
    return JSON.stringify(state);
};

export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        const response = await openrouter.systemOne({
            model: "respan/span-01",
            state: toSpanState(inputs.state),
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
        throw new Error(`Respan: Span-01 node error: ${error.message}`);
    }
};