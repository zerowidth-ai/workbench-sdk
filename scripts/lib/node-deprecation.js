/**
 * Shared deprecation / tombstoning helpers for the node generators.
 *
 * Why this exists: the generators used to DELETE every node whose model was no
 * longer returned by OpenRouter (cleanup_old_nodes). That silently breaks any
 * saved flow referencing the deleted node type. Instead we *tombstone* — keep
 * the node on disk but mark it `deprecated` — so flows still load and tooling
 * can surface a warning. Live models that OpenRouter itself flags as deprecated
 * or expiring also get stamped.
 *
 * Used by generate_llm_nodes.js / generate_embedding_nodes.js /
 * generate_rerank_nodes.js (and the eventual shared generator base).
 */
const fs = require('fs');
const path = require('path');

function todayISO(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

function readConfig(nodesDir, nodeName) {
  const p = path.join(nodesDir, nodeName, `${nodeName}.config.json`);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * Deprecation fields for a LIVE model that OpenRouter flags as deprecated or
 * expiring. Returns {} when the model is healthy (so a freshly rebuilt config
 * carries no stale deprecation). Preserves an existing `since`/`replacement`
 * so re-runs don't churn the date.
 *
 * @param {object} model - the OpenRouter model object
 * @param {object|null} existingConfig - the node's prior config.json, if any
 */
function modelDeprecationFields(model, existingConfig, today = todayISO()) {
  const flaggedDeprecated = !!model.deprecated;
  const expiration = model.expiration_date || null;
  if (!flaggedDeprecated && !expiration) return {};

  const prior = (existingConfig && existingConfig.deprecation) || {};
  return {
    deprecated: true,
    deprecation: {
      reason: flaggedDeprecated
        ? 'Marked deprecated by OpenRouter'
        : 'Scheduled for removal by the provider',
      since: prior.since || today,
      expiration_date: expiration,
      replacement: prior.replacement || null,
      source: 'openrouter'
    }
  };
}

/**
 * Tombstone existing nodes of `category` whose model_id is no longer present in
 * the live OpenRouter set. Keeps the node, marks it deprecated. Idempotent:
 * preserves an existing `since`. Skips nodes without a `model_id` (e.g. the
 * generic dynamic-model `embedding` node), so they're never touched.
 *
 * @returns {string[]} names of nodes that were tombstoned
 */
function tombstoneMissingNodes({ nodesDir, category, liveModelIds, dryRun = false, today = todayISO() }) {
  const tombstoned = [];
  if (!fs.existsSync(nodesDir)) return tombstoned;

  for (const dirent of fs.readdirSync(nodesDir, { withFileTypes: true })) {
    if (!dirent.isDirectory()) continue;
    const nodeName = dirent.name;
    const cfg = readConfig(nodesDir, nodeName);
    if (!cfg || cfg.category !== category) continue;
    if (!cfg.model_id) continue;                 // dynamic-model nodes: never tombstone
    if (liveModelIds.has(cfg.model_id)) continue; // still live (was/will be regenerated)

    const prior = cfg.deprecation || {};
    cfg.deprecated = true;
    cfg.deprecation = {
      reason: 'Model no longer available on OpenRouter',
      since: prior.since || today,
      expiration_date: prior.expiration_date || null,
      replacement: prior.replacement || null,
      source: 'openrouter'
    };
    tombstoned.push(nodeName);

    if (!dryRun) {
      const p = path.join(nodesDir, nodeName, `${nodeName}.config.json`);
      fs.writeFileSync(p, JSON.stringify(cfg, null, 2));
    }
  }
  return tombstoned;
}

module.exports = { tombstoneMissingNodes, modelDeprecationFields, todayISO, readConfig };
