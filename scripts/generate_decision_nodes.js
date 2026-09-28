const fs = require('fs');
const path = require('path');
const axios = require('axios');
const { tombstoneMissingNodes, modelDeprecationFields, readConfig } = require('./lib/node-deprecation');
const { isBatchVariant } = require('./lib/model-filters');

// Load environment variables from .env file
require('dotenv').config();

// Configuration
const BASE_DIR = path.dirname(path.resolve(__dirname));
const NODES_DIR = path.join(BASE_DIR, 'nodes');

// OpenRouter API configuration
const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1';
// The /models endpoint defaults to output_modalities=text; request decisions explicitly.
// "decisions" is the System One modality: models that take a state plus typed
// questions (noul / choice / score) and return typed answers via /systemone,
// rather than chat completions. TypeSafe's Jev was the first; Upstage, Respan
// and others serve the same contract.
const OPENROUTER_MODELS_URL = `${OPENROUTER_API_URL}/models?output_modalities=decisions`;

// Category used for all generated decision nodes.
const DECISION_CATEGORY = 'decision';

// Load configuration
function loadConfig() {
  const configPath = path.join(__dirname, 'decision-generator.config.json');
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (error) {
    console.warn('Warning: Could not load decision-generator.config.json, using defaults');
  }

  return {
    providers: { _all: { enabled: true, models: { filter: 'all_current' } } },
    generation: {
      category: DECISION_CATEGORY,
      include_tests: true,
      include_python: true,
      dry_run: false
    },
    output: { overwrite_existing: true, cleanup_old_nodes: true }
  };
}

class DecisionNodeGenerator {
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
    console.log('Fetching decision (System One) models from OpenRouter...');
    try {
      const headers = this.options.apiKey
        ? { Authorization: `Bearer ${this.options.apiKey}` }
        : {};
      const response = await axios.get(OPENROUTER_MODELS_URL, { headers });
      this.models = response.data.data || [];
      // Full live decision set, before filterModels() narrows this.models.
      this.liveModelIds = new Set(this.models.map(m => m.id));
      console.log(`Found ${this.models.length} models with decisions output modality`);
      return this.models;
    } catch (error) {
      console.error('Error fetching models from OpenRouter:', error.message);
      throw error;
    }
  }

  filterModels() {
    console.log('Filtering models...');
    const filtered = this.models.filter(model => {
      // Batch-only variants can't be called synchronously
      if (isBatchVariant(model)) return false;

      const provider = this.providerOf(model.id);

      if (!model.architecture?.output_modalities?.includes('decisions')) {
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
      // Deprecated-but-still-live models are kept (not excluded): generateNode
      // stamps them deprecated via modelDeprecationFields so they're flagged.

      return true;
    });

    console.log(`Filtered to ${filtered.length} decision models`);
    this.models = filtered;
    return filtered;
  }

  // OpenRouter alias ids are prefixed with "~" (e.g. ~typesafe/jev-latest).
  providerOf(modelId) {
    return modelId.replace(/^~/, '').split('/')[0].toLowerCase();
  }

  providerOverride(model) {
    return this.config.provider_overrides?.[this.providerOf(model.id)] || {};
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
        name: 'state',
        display_name: 'State',
        type: 'string or object or array or array of objects or array of strings or conversation or message',
        description: this.providerOverride(model).state_format === 'conversation_span'
          ? 'The conversation span to score: a conversation ending with an assistant reply (converted to { input, output } automatically), a single assistant message, or plain text. Other structured data is sent as JSON text.'
          : 'The content to evaluate: plain text, a conversation or message, or structured data (object/array) such as a record or application state. Questions can refer to nested fields by name in backticks.',
        required: true
      },
      {
        name: 'questions',
        display_name: 'Questions',
        type: 'object',
        description: 'Map of question id -> typed question. Each question has a type ("noul" = yes/no probability, "choice" = pick one option, "score" = rate on ordered levels), instructions, and criteria (noul: optional { true, false }; choice: { option: description|null }; score: ordered array of 2-10 level descriptions). Answers come back under the same ids.',
        required: true
      }
    ];
  }

  generateOutputs(model) {
    return [
      {
        name: 'answers',
        display_name: 'Answers',
        type: 'object',
        description: 'Typed answer per question id. noul: { type, noul }; choice: { type, choice, probabilities, confidence }; score: { type, score, legend, probabilities, confidence }'
      },
      {
        name: 'values',
        display_name: 'Values',
        type: 'object',
        description: 'Shortcut map of question id -> primary value (noul probability, chosen option, or score)'
      },
      {
        name: 'model',
        display_name: 'Model',
        type: 'string',
        description: 'The versioned model id that answered (aliases resolve to a specific version)'
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
        description: 'Total cost for this request (USD)'
      },
      {
        name: 'cost_itemized',
        display_name: 'Itemized Cost',
        type: 'array of objects',
        description: 'Detailed breakdown of costs'
      }
    ];
  }

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

  generateConfig(model) {
    const override = this.providerOverride(model);
    let description = model.description || `Answer typed questions about a state using ${model.name}`;
    if (override.note) description = `${description}\n\n${override.note}`;
    return {
      display_name: model.name,
      tagline: 'Answer typed questions about a state',
      description,
      category: this.config.generation.category,
      provider: this.providerOf(model.id),
      model_id: model.id,
      ...(model.alias_target?.slug && { alias_of: model.alias_target.slug }),
      context_length: model.context_length,
      supported_question_types: override.supported_question_types || ['noul', 'choice', 'score'],
      inputs: this.generateInputs(model),
      outputs: this.generateOutputs(model),
      pricing: this.generatePricing(model)
    };
  }

  // Converts workbench conversation/message shapes into the
  // { input: [messages], output: assistantMessage } span some decision models
  // (e.g. Respan) require, with string content only.
  jsSpanHelper() {
    return `// This model scores a conversation span: { input: [messages], output: assistantMessage },
// where every message has string content. Convert workbench conversation/message
// shapes into that; plain strings pass through; other data is sent as JSON text.
const SPAN_ROLES = { system: 'system', developer: 'system', user: 'user', assistant: 'assistant', tool: 'tool' };
const contentToText = (content) => {
    if (content === null || content === undefined) return '';
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
        return content
            .map(part => typeof part === 'string' ? part : (part?.text ?? (part?.type === 'image_url' ? '[image]' : JSON.stringify(part))))
            .join('\\n');
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
            throw new Error(\`this model scores a conversation span that ends with an assistant reply, but the last message has role "\${last.role}". Connect a conversation ending in an assistant message, or a string.\`);
        }
        return { input: messages.slice(0, -1).map(toSpanMessage), output: toSpanMessage(last) };
    }
    if (state !== null && typeof state === 'object' && !Array.isArray(state) && Array.isArray(state.input) && isMessage(state.output)) {
        return state; // already a span
    }
    return JSON.stringify(state);
};

`;
  }

  generateJSProcess(model) {
    const modelId = model.id;
    const isSpan = this.providerOverride(model).state_format === 'conversation_span';
    return `${isSpan ? this.jsSpanHelper() : ''}export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        const response = await openrouter.systemOne({
            model: ${JSON.stringify(modelId)},
            state: ${isSpan ? 'toSpanState(inputs.state)' : 'inputs.state'},
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
        throw new Error(\`${model.name} node error: \${error.message}\`);
    }
};`;
  }

  pySpanHelper() {
    return `
import json

# This model scores a conversation span: {"input": [messages], "output": assistant_message},
# where every message has string content. Convert workbench conversation/message
# shapes into that; plain strings pass through; other data is sent as JSON text.
_SPAN_ROLES = {"system": "system", "developer": "system", "user": "user", "assistant": "assistant", "tool": "tool"}


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("text") is not None:
                parts.append(str(part["text"]))
            elif isinstance(part, dict) and part.get("type") == "image_url":
                parts.append("[image]")
            else:
                parts.append(json.dumps(part))
        return "\\n".join(parts)
    return json.dumps(content)


def _is_message(m: Any) -> bool:
    return isinstance(m, dict) and isinstance(m.get("role"), str)


def _to_span_message(m: dict[str, Any]) -> dict[str, str]:
    text = _content_to_text(m.get("content"))
    if not text and m.get("tool_calls"):
        text = json.dumps(m["tool_calls"])
    return {"role": _SPAN_ROLES.get(m["role"], "user"), "content": text}


def _to_span_state(state: Any) -> Any:
    if isinstance(state, str):
        return state
    if _is_message(state) or (isinstance(state, list) and state and all(_is_message(m) for m in state)):
        messages = state if isinstance(state, list) else [state]
        last = messages[-1]
        if last["role"] != "assistant":
            raise ValueError(
                "this model scores a conversation span that ends with an assistant reply, "
                f"but the last message has role \\"{last['role']}\\". Connect a conversation "
                "ending in an assistant message, or a string."
            )
        return {"input": [_to_span_message(m) for m in messages[:-1]], "output": _to_span_message(last)}
    if isinstance(state, dict) and isinstance(state.get("input"), list) and _is_message(state.get("output")):
        return state  # already a span
    return json.dumps(state)
`;
  }

  generatePythonProcess(model) {
    const modelId = model.id;
    const isSpan = this.providerOverride(model).state_format === 'conversation_span';
    return `"""
${model.name} - Decision (System One) node for the zv1 engine.
"""

from typing import Any
${isSpan ? this.pySpanHelper() : ''}

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the ${model.name} decision node.

    Args:
        inputs: Node inputs containing the state and a map of typed questions.
        settings: Node settings (unused for decision nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with typed answers, primary values, model, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    response = await openrouter.system_one(
        model=${JSON.stringify(modelId)},
        state=${isSpan ? '_to_span_state(inputs.get("state"))' : 'inputs.get("state")'},
        questions=inputs.get("questions"),
        node_config=node_config,
        engine_config=config,
    )

    # Primary value per answer type, for easy wiring downstream
    answers = response.get("answers") or {}
    values = {
        qid: (answer.get(answer.get("type")) if isinstance(answer, dict) else None)
        for qid, answer in answers.items()
    }

    return {
        "answers": answers,
        "values": values,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }`;
  }

  generateTests(model) {
    const types = this.providerOverride(model).supported_question_types || ['noul', 'choice', 'score'];
    const tests = [
      {
        description: 'Noul question on a text state',
        inputs: {
          state: 'Help! My payouts have been failing for 3 days.',
          questions: {
            is_urgent: { type: 'noul', instructions: 'Does this convey urgency?' }
          }
        },
        expectedSchema: {
          answers: { type: 'object' },
          values: { type: 'object' },
          model: { type: 'string' },
          usage: { type: 'object' }
        }
      }
    ];
    // Conversations are the SDK's standard chat shape; every decision node must accept one
    tests.push({
      description: 'Noul question on a conversation state',
      inputs: {
        state: [
          { role: 'user', content: [{ type: 'text', text: 'I was charged twice for my subscription.' }] },
          { role: 'assistant', content: 'I am sorry about that, I have issued a refund for the duplicate charge.' }
        ],
        questions: {
          refund_issued: { type: 'noul', instructions: 'Did the assistant issue a refund?' }
        }
      },
      expectedSchema: {
        answers: { type: 'object' },
        values: { type: 'object' }
      }
    });
    if (types.includes('choice') && types.includes('score')) {
      tests.push({
        description: 'Choice and score questions on a structured state',
        inputs: {
          state: { channel: 'email', message: 'I was charged twice for my subscription and I am furious.' },
          questions: {
            department: {
              type: 'choice',
              instructions: 'Which team should handle `message`?',
              criteria: { billing: 'Payments, invoicing, refunds', technical: 'Bugs, outages, integrations', sales: null }
            },
            frustration: {
              type: 'score',
              instructions: 'How frustrated is the customer?',
              criteria: ['Calm', 'Frustrated', 'Very angry']
            }
          }
        },
        expectedSchema: {
          answers: { type: 'object' },
          values: { type: 'object' }
        }
      });
    }
    return tests;
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

  getExistingDecisionNodes() {
    const existingNodes = [];
    if (!fs.existsSync(NODES_DIR)) return existingNodes;
    for (const dirent of fs.readdirSync(NODES_DIR, { withFileTypes: true })) {
      if (!dirent.isDirectory()) continue;
      const nodeName = dirent.name;
      const configPath = path.join(NODES_DIR, nodeName, `${nodeName}.config.json`);
      if (fs.existsSync(configPath)) {
        try {
          const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
          if (config.category === DECISION_CATEGORY) existingNodes.push(nodeName);
        } catch (error) {
          console.warn(`Warning: Could not read config for ${nodeName}: ${error.message}`);
        }
      }
    }
    return existingNodes;
  }

  removeExistingDecisionNodes() {
    const existing = this.getExistingDecisionNodes();
    console.log(`Found ${existing.length} existing decision nodes to remove`);
    console.log(`Will generate ${this.models.length} new decision nodes`);
    for (const nodeName of existing) {
      const nodeDir = path.join(NODES_DIR, nodeName);
      if (fs.existsSync(nodeDir)) {
        if (!this.options.dryRun) {
          fs.rmSync(nodeDir, { recursive: true });
          console.log(`Removed existing decision node: ${nodeName}`);
        } else {
          console.log(`Would remove existing decision node: ${nodeName}`);
        }
      }
    }
  }

  async generate() {
    console.log('Starting decision node generation...\n');
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

    console.log(`\nGeneration complete! Generated ${this.generatedNodes.length} decision nodes.`);
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

  const generator = new DecisionNodeGenerator(options);
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

module.exports = DecisionNodeGenerator;
