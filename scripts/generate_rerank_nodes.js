const fs = require('fs');
const path = require('path');
const axios = require('axios');
const { tombstoneMissingNodes, modelDeprecationFields, readConfig } = require('./lib/node-deprecation');

// Load environment variables from .env file
require('dotenv').config();

// Configuration
const BASE_DIR = path.dirname(path.resolve(__dirname));
const NODES_DIR = path.join(BASE_DIR, 'nodes');

// OpenRouter API configuration
const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1';
// The /models endpoint defaults to output_modalities=text; request rerank explicitly.
const OPENROUTER_MODELS_URL = `${OPENROUTER_API_URL}/models?output_modalities=rerank`;

// Category used for all generated rerank nodes.
const RERANK_CATEGORY = 'rerank';

// Load configuration
function loadConfig() {
  const configPath = path.join(__dirname, 'rerank-generator.config.json');
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (error) {
    console.warn('Warning: Could not load rerank-generator.config.json, using defaults');
  }

  return {
    providers: { _all: { enabled: true, models: { filter: 'all_current' } } },
    generation: {
      category: RERANK_CATEGORY,
      include_tests: true,
      include_python: true,
      dry_run: false
    },
    output: { overwrite_existing: true, cleanup_old_nodes: true }
  };
}

class RerankNodeGenerator {
  constructor(options = {}) {
    this.config = loadConfig();
    this.options = {
      apiKey: options.apiKey || process.env.OPENROUTER_API_KEY,
      baseUrl: options.baseUrl || OPENROUTER_API_URL,
      dryRun: options.dryRun || this.config.generation.dry_run,
      ...options
    };
    this.models = [];
    this.generatedNodes = [];
  }

  includesAllProviders() {
    return !!this.config.providers?._all?.enabled;
  }

  async fetchModels() {
    console.log('Fetching rerank models from OpenRouter...');
    try {
      const headers = this.options.apiKey
        ? { Authorization: `Bearer ${this.options.apiKey}` }
        : {};
      const response = await axios.get(OPENROUTER_MODELS_URL, { headers });
      this.models = response.data.data || [];
      // Full live rerank set, before filterModels() narrows this.models.
      this.liveModelIds = new Set(this.models.map(m => m.id));
      console.log(`Found ${this.models.length} models with rerank output modality`);
      return this.models;
    } catch (error) {
      console.error('Error fetching models from OpenRouter:', error.message);
      throw error;
    }
  }

  filterModels() {
    console.log('Filtering models...');
    const filtered = this.models.filter(model => {
      const provider = model.id.split('/')[0].toLowerCase();

      if (!model.architecture?.output_modalities?.includes('rerank')) {
        return false;
      }

      if (!this.includesAllProviders()) {
        const providerConfig = this.config.providers[provider];
        if (!providerConfig || !providerConfig.enabled) return false;
        if (providerConfig.models?.filter === 'specific' &&
            !providerConfig.models.specific_models?.includes(model.id)) {
          return false;
        }
      }

      if (this.config.generation?.exclude_free && model.id.includes(':free')) return false;
      if (this.config.generation?.exclude_deprecated !== false && model.deprecated) return false;

      return true;
    });

    console.log(`Filtered to ${filtered.length} rerank models`);
    this.models = filtered;
    return filtered;
  }

  generateNodeName(modelId) {
    return modelId
      .replace(/[^a-zA-Z0-9]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase();
  }

  generateInputs(model) {
    return [
      {
        name: 'query',
        display_name: 'Query',
        type: 'string',
        description: 'The search query to rank documents against',
        required: true
      },
      {
        name: 'documents',
        display_name: 'Documents',
        type: 'array',
        description: 'Candidate documents to rerank. Accepts an array of strings, or an array of objects (e.g. search results) — for objects, text is read from text_field or common fields like content/text.',
        required: true
      },
      {
        name: 'top_n',
        display_name: 'Top N',
        type: 'number',
        description: 'Optional: return only the top N most relevant documents',
        default: null
      },
      {
        name: 'text_field',
        display_name: 'Text Field',
        type: 'string',
        description: 'Optional: when documents are objects, which field holds the text to rank (defaults to trying content, text, document, page_content, chunk, body)',
        default: null
      }
    ];
  }

  generateOutputs(model) {
    return [
      {
        name: 'results',
        display_name: 'Results',
        type: 'array',
        description: 'Reranked results, highest relevance first: { index, relevance_score, document } where document is the original input item'
      },
      {
        name: 'ranked_documents',
        display_name: 'Ranked Documents',
        type: 'array',
        description: 'The original documents reordered by relevance (highest first)'
      },
      {
        name: 'top_document',
        display_name: 'Top Document',
        type: 'any',
        description: 'The single most relevant document'
      },
      {
        name: 'usage',
        display_name: 'Usage',
        type: 'object',
        description: 'Usage / billed units reported by the provider (if any)'
      },
      {
        name: 'cost_total',
        display_name: 'Total Cost',
        type: 'number',
        description: 'Total cost for this request (USD), when token usage is reported'
      },
      {
        name: 'cost_itemized',
        display_name: 'Itemized Cost',
        type: 'array',
        description: 'Detailed breakdown of costs'
      }
    ];
  }

  // Rerank pricing on OpenRouter is per "search unit", not token-metered
  // (models report prompt/completion = 0). Keep items for parity; cost is
  // only computed at runtime if the API returns token usage.
  generatePricing(model) {
    const pricing = model.pricing || {};
    return {
      reference: 'https://openrouter.ai/models',
      note: 'Rerank is typically billed per search (1 query + up to ~100 docs), not per token. OpenRouter does not expose a per-token rerank price.',
      items: [
        {
          key: 'input_cost_per_million',
          label: 'Input Tokens (per 1M)',
          cost: parseFloat(pricing.prompt || '0') * 1_000_000,
          currency: 'USD'
        },
        {
          key: 'output_cost_per_million',
          label: 'Output Tokens (per 1M)',
          cost: parseFloat(pricing.completion || '0') * 1_000_000,
          currency: 'USD'
        }
      ]
    };
  }

  generateConfig(model) {
    const provider = model.id.split('/')[0].toLowerCase();
    return {
      display_name: model.name,
      tagline: 'Rerank documents by relevance',
      description: model.description || `Rerank documents against a query using ${model.name}`,
      category: this.config.generation.category,
      provider: provider,
      model_id: model.id,
      context_length: model.context_length,
      inputs: this.generateInputs(model),
      outputs: this.generateOutputs(model),
      pricing: this.generatePricing(model)
    };
  }

  generateJSProcess(model) {
    const modelId = model.id;
    return `export default async ({inputs, settings, config, nodeConfig}) => {
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
            model: "${modelId}",
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
        throw new Error(\`${model.name} node error: \${error.message}\`);
    }
};`;
  }

  generatePythonProcess(model) {
    const modelId = model.id;
    return `"""
${model.name} - Rerank node for the zv1 engine.
"""

from typing import Any


def _to_text(doc: Any, text_field: str | None) -> str:
    """Extract the text to rank from a document (string or object)."""
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        if text_field and doc.get(text_field) is not None:
            return str(doc[text_field])
        for field in ("content", "text", "document", "page_content", "chunk", "body"):
            if doc.get(field) is not None:
                return str(doc[field])
        import json as _json
        return _json.dumps(doc)
    return str(doc)


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the ${model.name} rerank node.

    Args:
        inputs: Node inputs containing query and documents to rerank.
        settings: Node settings (unused for rerank nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with reranked results, ordered documents, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    documents = inputs.get("documents")
    if not isinstance(documents, list):
        raise ValueError("documents must be an array")

    text_field = inputs.get("text_field")
    texts = [_to_text(doc, text_field) for doc in documents]

    params: dict[str, Any] = {}
    if inputs.get("top_n") is not None:
        params["top_n"] = inputs.get("top_n")

    response = await openrouter.rerank(
        model="${modelId}",
        query=inputs.get("query"),
        documents=texts,
        node_config=node_config,
        engine_config=config,
        **params,
    )

    # Reattach original documents by index, preserving the API's relevance order
    results = [
        {
            "index": r.get("index"),
            "relevance_score": r.get("relevance_score"),
            "document": documents[r.get("index")] if r.get("index") is not None else None,
        }
        for r in (response.get("results") or [])
    ]

    return {
        "results": results,
        "ranked_documents": [r["document"] for r in results],
        "top_document": results[0]["document"] if results else None,
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }`;
  }

  generateTests(model) {
    return [
      {
        description: 'Rerank an array of strings',
        inputs: {
          query: 'What is the capital of France?',
          documents: [
            'The Eiffel Tower is in Paris.',
            'Paris is the capital of France.',
            'Bananas are a good source of potassium.'
          ]
        },
        expectedSchema: {
          results: { type: 'array' },
          ranked_documents: { type: 'array' },
          usage: { type: 'object' }
        }
      },
      {
        description: 'Rerank objects and keep top N',
        inputs: {
          query: 'database indexing',
          documents: [
            { content: 'B-tree indexes speed up range queries.' },
            { content: 'The mitochondria is the powerhouse of the cell.' }
          ],
          top_n: 1
        },
        expectedSchema: {
          results: { type: 'array' },
          top_document: { type: 'object' }
        }
      }
    ];
  }

  generateNode(model) {
    const nodeName = this.generateNodeName(model.id);
    const nodeDir = path.join(NODES_DIR, nodeName);
    console.log(`Generating node: ${nodeName}`);

    // Capture prior config before deletion to preserve deprecation history.
    const priorConfig = readConfig(NODES_DIR, nodeName);

    if (!this.options.dryRun) {
      if (fs.existsSync(nodeDir)) fs.rmSync(nodeDir, { recursive: true });
      fs.mkdirSync(nodeDir, { recursive: true });
    }

    const config = this.generateConfig(model);
    // Stamp deprecation if OpenRouter flags this (live) model as deprecated/expiring.
    Object.assign(config, modelDeprecationFields(model, priorConfig));

    const files = [
      { path: path.join(nodeDir, `${nodeName}.config.json`), content: JSON.stringify(config, null, 2) },
      { path: path.join(nodeDir, `${nodeName}.process.js`), content: this.generateJSProcess(model) },
      { path: path.join(nodeDir, `${nodeName}.process.py`), content: this.generatePythonProcess(model) },
      { path: path.join(nodeDir, `${nodeName}.tests.json`), content: JSON.stringify(this.generateTests(model), null, 2) }
    ];

    for (const file of files) {
      if (!this.options.dryRun) {
        fs.writeFileSync(file.path, file.content);
        console.log(`  Created: ${path.relative(BASE_DIR, file.path)}`);
      } else {
        console.log(`  Would create: ${path.relative(BASE_DIR, file.path)}`);
      }
    }

    this.generatedNodes.push({ name: nodeName, model: model.id });
  }

  getExistingRerankNodes() {
    const existingNodes = [];
    if (!fs.existsSync(NODES_DIR)) return existingNodes;
    for (const dirent of fs.readdirSync(NODES_DIR, { withFileTypes: true })) {
      if (!dirent.isDirectory()) continue;
      const nodeName = dirent.name;
      const configPath = path.join(NODES_DIR, nodeName, `${nodeName}.config.json`);
      if (fs.existsSync(configPath)) {
        try {
          const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
          if (config.category === RERANK_CATEGORY) existingNodes.push(nodeName);
        } catch (error) {
          console.warn(`Warning: Could not read config for ${nodeName}: ${error.message}`);
        }
      }
    }
    return existingNodes;
  }

  removeExistingRerankNodes() {
    const existing = this.getExistingRerankNodes();
    console.log(`Found ${existing.length} existing rerank nodes to remove`);
    console.log(`Will generate ${this.models.length} new rerank nodes`);
    for (const nodeName of existing) {
      const nodeDir = path.join(NODES_DIR, nodeName);
      if (fs.existsSync(nodeDir)) {
        if (!this.options.dryRun) {
          fs.rmSync(nodeDir, { recursive: true });
          console.log(`Removed existing rerank node: ${nodeName}`);
        } else {
          console.log(`Would remove existing rerank node: ${nodeName}`);
        }
      }
    }
  }

  async generate() {
    console.log('Starting rerank node generation...\n');
    await this.fetchModels();
    const filteredModels = this.filterModels();

    for (const model of filteredModels) {
      try {
        this.generateNode(model);
      } catch (error) {
        console.error(`Error generating node for ${model.id}:`, error.message);
      }
    }

    // Tombstone (DON'T delete) nodes whose model is no longer on OpenRouter, so
    // saved flows referencing them still load.
    if (this.config.output.cleanup_old_nodes) {
      const tombstoned = tombstoneMissingNodes({
        nodesDir: NODES_DIR,
        category: this.config.generation.category,
        liveModelIds: this.liveModelIds || new Set(),
        dryRun: this.options.dryRun
      });
      console.log(`Tombstoned ${tombstoned.length} node(s) for models no longer on OpenRouter (kept + marked deprecated).`);
      if (tombstoned.length) console.log('  ' + tombstoned.join('\n  '));
    } else {
      console.log('Skipping tombstone pass (cleanup_old_nodes: false)');
    }

    console.log(`\nGeneration complete! Generated ${this.generatedNodes.length} rerank nodes.`);
    if (this.options.dryRun) {
      console.log('This was a dry run. No files were actually created.');
    } else {
      console.log('Run the sync script to distribute nodes to SDKs:');
      console.log('  python scripts/sync_sdks.py');
    }
    return this.generatedNodes;
  }
}

async function main() {
  const args = process.argv.slice(2);
  const config = loadConfig();

  const options = {
    dryRun: args.includes('--dry-run') || config.generation.dry_run,
    apiKey: process.env.OPENROUTER_API_KEY,
    baseUrl: process.env.OPENROUTER_BASE_URL || OPENROUTER_API_URL
  };

  if (!options.apiKey) {
    console.warn('Warning: OPENROUTER_API_KEY not set. Model listing will still work,');
    console.warn('but generated nodes require an OpenRouter key at runtime.\n');
  }

  console.log('Using configuration:', JSON.stringify(config, null, 2));

  const generator = new RerankNodeGenerator(options);
  try {
    await generator.generate();
  } catch (error) {
    console.error('Generation failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = RerankNodeGenerator;
