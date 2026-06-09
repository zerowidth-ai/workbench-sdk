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
// The /models endpoint defaults to output_modalities=text, which HIDES embedding
// models. We must explicitly request the embeddings modality to see them.
const OPENROUTER_MODELS_URL = `${OPENROUTER_API_URL}/models?output_modalities=embeddings`;

// Category used for all generated embedding nodes. Mirrors the "llm" category
// used by generate_llm_nodes.js so cleanup can target embedding nodes only.
const EMBEDDING_CATEGORY = 'embedding';

// Load configuration
function loadConfig() {
  const configPath = path.join(__dirname, 'embedding-generator.config.json');
  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(configData);
    }
  } catch (error) {
    console.warn('Warning: Could not load embedding-generator.config.json, using defaults');
  }

  // Default configuration: include every provider OpenRouter exposes embeddings for.
  return {
    providers: { _all: { enabled: true, models: { filter: 'all_current' } } },
    generation: {
      category: EMBEDDING_CATEGORY,
      include_tests: true,
      include_python: true,
      include_cost_calculation: true,
      dry_run: false
    },
    output: {
      overwrite_existing: true,
      cleanup_old_nodes: true
    }
  };
}

class EmbeddingNodeGenerator {
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

  /**
   * Whether the generator is configured to include every provider.
   * Triggered by the special "_all" provider key.
   */
  includesAllProviders() {
    return !!this.config.providers?._all?.enabled;
  }

  /**
   * Fetch all embedding models from OpenRouter
   */
  async fetchModels() {
    console.log('Fetching embedding models from OpenRouter...');

    try {
      // Listing models is public, but send the key if we have one.
      const headers = this.options.apiKey
        ? { Authorization: `Bearer ${this.options.apiKey}` }
        : {};
      const response = await axios.get(OPENROUTER_MODELS_URL, { headers });
      this.models = response.data.data || [];
      // Full live embedding set, before filterModels() narrows this.models.
      this.liveModelIds = new Set(this.models.map(m => m.id));

      console.log(`Found ${this.models.length} models with embeddings output modality`);
      return this.models;
    } catch (error) {
      console.error('Error fetching models from OpenRouter:', error.message);
      throw error;
    }
  }

  /**
   * Filter to embedding models for enabled providers
   */
  filterModels() {
    console.log('Filtering models...');

    const filtered = this.models.filter(model => {
      const provider = model.id.split('/')[0].toLowerCase();

      // Must actually be an embeddings model (defensive — the API query already filters)
      if (!model.architecture?.output_modalities?.includes('embeddings')) {
        return false;
      }

      // Provider gating. "_all" means include every provider.
      if (!this.includesAllProviders()) {
        const providerConfig = this.config.providers[provider];
        if (!providerConfig || !providerConfig.enabled) {
          return false;
        }

        // Specific model list within provider
        if (providerConfig.models?.filter === 'specific') {
          if (!providerConfig.models.specific_models?.includes(model.id)) {
            return false;
          }
        }

        // Exclude patterns within provider
        if (providerConfig.models?.exclude_patterns) {
          for (const pattern of providerConfig.models.exclude_patterns) {
            if (this.matchesPattern(model.id, pattern)) {
              return false;
            }
          }
        }
      }

      // Optionally skip ":free" variants
      if (this.config.generation?.exclude_free && model.id.includes(':free')) {
        return false;
      }

      // Optionally skip deprecated models
      if (this.config.generation?.exclude_deprecated !== false && model.deprecated) {
        return false;
      }

      return true;
    });

    console.log(`Filtered to ${filtered.length} embedding models`);
    this.models = filtered;
    return filtered;
  }

  /**
   * Check if a model ID matches a glob-ish pattern
   */
  matchesPattern(modelId, pattern) {
    const regexPattern = pattern
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      .replace(/\\\*/g, '.*')
      .replace(/\\\?/g, '.');
    const regex = new RegExp(regexPattern, 'i');
    return regex.test(modelId);
  }

  /**
   * Generate node name from model ID (kebab-case)
   */
  generateNodeName(modelId) {
    return modelId
      .replace(/[^a-zA-Z0-9]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase();
  }

  /**
   * Inputs for an embedding node. Unlike chat models, the meaningful inputs are
   * fixed (the /embeddings endpoint ignores chat sampling params), so we don't
   * map OpenRouter's supported_parameters here.
   */
  generateInputs(model) {
    const inputs = [
      {
        name: 'input',
        display_name: 'Input',
        type: 'string or array of strings',
        description: 'Text, or an array of texts, to convert into embedding vectors',
        required: true
      },
      {
        name: 'dimensions',
        display_name: 'Dimensions',
        type: 'number',
        description: 'Optional: reduce the output vector size. Only some models support this (e.g. OpenAI text-embedding-3-*, Gemini, Qwen3). Leave null for the model default.',
        default: null
      },
      {
        name: 'encoding_format',
        display_name: 'Encoding Format',
        type: 'string',
        description: 'Optional: "float" (default) or "base64"',
        default: null
      }
    ];

    return inputs;
  }

  /**
   * Outputs for an embedding node
   */
  generateOutputs(model) {
    return [
      {
        name: 'embedding',
        display_name: 'Embedding',
        type: 'array',
        description: 'The embedding vector for the first (or only) input'
      },
      {
        name: 'embeddings',
        display_name: 'Embeddings',
        type: 'array',
        description: 'Array of embedding vectors, one per input (in input order)'
      },
      {
        name: 'dimensions',
        display_name: 'Dimensions',
        type: 'number',
        description: 'Length of each embedding vector'
      },
      {
        name: 'usage',
        display_name: 'Token Usage',
        type: 'object',
        description: 'Token usage statistics'
      },
      {
        name: 'cost_total',
        display_name: 'Total Cost',
        type: 'number',
        description: 'Total cost for processing this request (USD)'
      },
      {
        name: 'cost_itemized',
        display_name: 'Itemized Cost',
        type: 'array',
        description: 'Detailed breakdown of costs'
      }
    ];
  }

  /**
   * Generate pricing information. Embeddings only bill input (prompt) tokens;
   * output cost is kept at 0 for parity with calculateCosts().
   */
  generatePricing(model) {
    const pricing = model.pricing || {};
    return {
      reference: 'https://openrouter.ai/models',
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

  /**
   * Generate config.json content
   */
  generateConfig(model) {
    const provider = model.id.split('/')[0].toLowerCase();

    return {
      display_name: model.name,
      tagline: 'Generate embeddings',
      description: model.description || `Generate vector embeddings using ${model.name}`,
      category: this.config.generation.category,
      provider: provider,
      model_id: model.id,
      context_length: model.context_length,
      input_modalities: model.architecture?.input_modalities || ['text'],
      inputs: this.generateInputs(model),
      outputs: this.generateOutputs(model),
      pricing: this.generatePricing(model)
    };
  }

  /**
   * Generate JavaScript process file
   */
  generateJSProcess(model) {
    const modelId = model.id;
    return `export default async ({inputs, settings, config, nodeConfig}) => {
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
            model: "${modelId}",
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
        throw new Error(\`${model.name} node error: \${error.message}\`);
    }
};`;
  }

  /**
   * Generate Python process file
   */
  generatePythonProcess(model) {
    const modelId = model.id;
    return `"""
${model.name} - Embedding node for the zv1 engine.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the ${model.name} embedding node.

    Args:
        inputs: Node inputs containing the text/array to embed and options.
        settings: Node settings (unused for embedding nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with embedding, embeddings, dimensions, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    # Build optional parameters (only sent when provided)
    params: dict[str, Any] = {}
    if inputs.get("dimensions") is not None:
        params["dimensions"] = inputs.get("dimensions")
    if inputs.get("encoding_format") is not None:
        params["encoding_format"] = inputs.get("encoding_format")

    response = await openrouter.create_embedding(
        model="${modelId}",
        input=inputs.get("input"),
        node_config=node_config,
        engine_config=config,
        **params,
    )

    return {
        "embedding": response.get("embedding"),
        "embeddings": response.get("embeddings"),
        "dimensions": response.get("dimensions"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }`;
  }

  /**
   * Generate test file
   */
  generateTests(model) {
    return [
      {
        description: 'Embed a single string',
        inputs: {
          input: 'The quick brown fox jumps over the lazy dog.'
        },
        expectedSchema: {
          embedding: { type: 'array' },
          dimensions: { type: 'number', minimum: 1 },
          usage: { type: 'object' },
          cost_total: { type: 'number', minimum: 0 },
          cost_itemized: { type: 'array' }
        }
      },
      {
        description: 'Embed an array of strings',
        inputs: {
          input: ['first piece of text', 'second piece of text']
        },
        expectedSchema: {
          embeddings: { type: 'array' },
          dimensions: { type: 'number', minimum: 1 },
          usage: { type: 'object' }
        }
      }
    ];
  }

  /**
   * Generate a single node (4 files)
   */
  generateNode(model) {
    const nodeName = this.generateNodeName(model.id);
    const nodeDir = path.join(NODES_DIR, nodeName);

    console.log(`Generating node: ${nodeName}`);

    // Capture prior config before deletion to preserve deprecation history.
    const priorConfig = readConfig(NODES_DIR, nodeName);

    if (!this.options.dryRun) {
      if (fs.existsSync(nodeDir)) {
        fs.rmSync(nodeDir, { recursive: true });
      }
      fs.mkdirSync(nodeDir, { recursive: true });
    }

    const config = this.generateConfig(model);
    // Stamp deprecation if OpenRouter flags this (live) model as deprecated/expiring.
    Object.assign(config, modelDeprecationFields(model, priorConfig));
    const jsProcess = this.generateJSProcess(model);
    const pythonProcess = this.generatePythonProcess(model);
    const tests = this.generateTests(model);

    const files = [
      { path: path.join(nodeDir, `${nodeName}.config.json`), content: JSON.stringify(config, null, 2) },
      { path: path.join(nodeDir, `${nodeName}.process.js`), content: jsProcess },
      { path: path.join(nodeDir, `${nodeName}.process.py`), content: pythonProcess },
      { path: path.join(nodeDir, `${nodeName}.tests.json`), content: JSON.stringify(tests, null, 2) }
    ];

    for (const file of files) {
      if (!this.options.dryRun) {
        fs.writeFileSync(file.path, file.content);
        console.log(`  Created: ${path.relative(BASE_DIR, file.path)}`);
      } else {
        console.log(`  Would create: ${path.relative(BASE_DIR, file.path)}`);
      }
    }

    this.generatedNodes.push({ name: nodeName, model: model.id, config });
  }

  /**
   * Find existing embedding nodes (category === EMBEDDING_CATEGORY)
   */
  getExistingEmbeddingNodes() {
    const existingNodes = [];
    if (!fs.existsSync(NODES_DIR)) return existingNodes;

    const nodeDirs = fs.readdirSync(NODES_DIR, { withFileTypes: true });
    for (const dirent of nodeDirs) {
      if (!dirent.isDirectory()) continue;
      const nodeName = dirent.name;
      const configPath = path.join(NODES_DIR, nodeName, `${nodeName}.config.json`);
      if (fs.existsSync(configPath)) {
        try {
          const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
          if (config.category === EMBEDDING_CATEGORY) {
            existingNodes.push(nodeName);
          }
        } catch (error) {
          console.warn(`Warning: Could not read config for ${nodeName}: ${error.message}`);
        }
      }
    }
    return existingNodes;
  }

  /**
   * Remove existing embedding nodes when cleanup_old_nodes is enabled
   */
  removeExistingEmbeddingNodes() {
    const existing = this.getExistingEmbeddingNodes();
    console.log(`Found ${existing.length} existing embedding nodes to remove`);
    console.log(`Will generate ${this.models.length} new embedding nodes`);

    for (const nodeName of existing) {
      const nodeDir = path.join(NODES_DIR, nodeName);
      if (fs.existsSync(nodeDir)) {
        if (!this.options.dryRun) {
          fs.rmSync(nodeDir, { recursive: true });
          console.log(`Removed existing embedding node: ${nodeName}`);
        } else {
          console.log(`Would remove existing embedding node: ${nodeName}`);
        }
      }
    }
  }

  /**
   * Main generation process
   */
  async generate() {
    console.log('Starting embedding node generation...\n');

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

    console.log(`\nGeneration complete! Generated ${this.generatedNodes.length} embedding nodes.`);

    if (this.options.dryRun) {
      console.log('This was a dry run. No files were actually created.');
    } else {
      console.log('Run the sync script to distribute nodes to SDKs:');
      console.log('  python scripts/sync_sdks.py');
    }

    return this.generatedNodes;
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  const config = loadConfig();

  const options = {
    dryRun: args.includes('--dry-run') || config.generation.dry_run,
    apiKey: process.env.OPENROUTER_API_KEY,
    baseUrl: process.env.OPENROUTER_BASE_URL || OPENROUTER_API_URL
  };

  // Listing models works without a key, but the rest of the pipeline (and the
  // generated nodes at runtime) need one, so warn rather than hard-fail.
  if (!options.apiKey) {
    console.warn('Warning: OPENROUTER_API_KEY not set. Model listing will still work,');
    console.warn('but generated nodes require an OpenRouter key at runtime.\n');
  }

  console.log('Using configuration:', JSON.stringify(config, null, 2));

  const generator = new EmbeddingNodeGenerator(options);

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

module.exports = EmbeddingNodeGenerator;
