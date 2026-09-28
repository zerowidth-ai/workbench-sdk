/**
 * Shared model filters for the node generators.
 */

/**
 * OpenRouter lists ":batch" variants (e.g. openai/gpt-4o-mini:batch) that only
 * work through its asynchronous batch API. The chat/completions, /embeddings,
 * /rerank and /systemone endpoints reject them, so a generated node would
 * always fail at runtime.
 */
function isBatchVariant(model) {
  return /:batch$/i.test(model.id || '');
}

module.exports = { isBatchVariant };
