const fs = require('fs');
const path = require('path');
const axios = require('axios');

// Load environment variables from .env file
require('dotenv').config();

// Configuration
const BASE_DIR = path.dirname(path.resolve(__dirname));
const NODES_DIR = path.join(BASE_DIR, 'nodes');
const ENGINES_DIR = path.join(BASE_DIR, 'engines');
const NODEJS_ENGINE_DIR = path.join(ENGINES_DIR, 'nodejs');
const NODEJS_INTEGRATIONS_DIR = path.join(NODEJS_ENGINE_DIR, 'integrations');

// OpenRouter API configuration
const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1';
const OPENROUTER_MODELS_URL = `${OPENROUTER_API_URL}/models`;

// Load configuration
function loadConfig() {
  const configPath = path.join(__dirname, 'generator.config.json');
  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(configData);
    }
  } catch (error) {
    console.warn('Warning: Could not load generator.config.json, using defaults');
  }
  
  // Default configuration
  return {
    providers: {
      openai: {
        enabled: true,
        models: {
          filter: "all_current"
        }
      },
      anthropic: {
        enabled: true,
        models: {
          filter: "all_current"
        }
      }
    },
    generation: {
      category: "llm",
      include_tests: true,
      include_python: true,
      include_cost_calculation: true,
      dry_run: false
    },
    output: {
      overwrite_existing: true,
      backup_existing: false,
      create_provider_folders: false,
      cleanup_old_nodes: true
    },
    muted_inputs: [
      "structured_outputs"
    ],
    muted_outputs: [
      "native_finish_reason"
    ]
  };
}

// Parameter mappings from OpenRouter to our system
const PARAMETER_MAPPINGS = {
  'tools': {
    type: 'tool',
    description: 'Array of tools to use',
    default: null,
    allow_multiple: true
  },
  'tool_choice': {
    type: 'string',
    description: 'Tool selection control',
    default: null
  },
  'response_format': {
    type: 'string or object',
    description: 'Output format specification',
    default: null
  },
  'stop': {
    type: 'string or array',
    description: 'Custom stop sequences',
    default: null
  },
  'temperature': {
    type: 'number',
    description: 'Controls randomness (0-2)',
    default: null
  },
  'top_p': {
    type: 'number', 
    description: 'Controls diversity via nucleus sampling',
    default: null
  },
  'max_tokens': {
    type: 'number',
    description: 'Maximum tokens to generate',
    default: null
  },
  'frequency_penalty': {
    type: 'number',
    description: 'Reduces repetition (-2 to 2)',
    default: null
  },
  'presence_penalty': {
    type: 'number',
    description: 'Encourages new topics (-2 to 2)',
    default: null
  },
  'seed': {
    type: 'number',
    description: 'Deterministic outputs',
    default: null
  },
  'reasoning': {
    type: 'boolean',
    description: 'Internal reasoning mode',
    default: null
  },
  'include_reasoning': {
    type: 'boolean',
    description: 'Include reasoning in response',
    default: null
  },
  'modalities': {
    type: 'array',
    description: 'Output modalities to request (e.g., ["image", "text"])',
    default: null
  },
  'image_config': {
    type: 'object',
    description: 'Image generation configuration (aspect_ratio, etc.)',
    default: null
  },
  // 'structured_outputs': {
  //   type: 'string or object',
  //   description: 'JSON schema enforcement',
  //   default: null
  // }
};

class LLMNodeGenerator {
  constructor(options = {}) {
    this.config = loadConfig();
    this.options = {
      apiKey: options.apiKey || process.env.OPENROUTER_API_KEY,
      baseUrl: options.baseUrl || 'https://openrouter.ai/api/v1',
      dryRun: options.dryRun || this.config.generation.dry_run,
      ...options
    };
    
    this.models = [];
    this.generatedNodes = [];
  }

  /**
   * Fetch all available models from OpenRouter
   */
  async fetchModels() {
    console.log('Fetching models from OpenRouter...');
    
    try {
      const response = await axios.get(OPENROUTER_MODELS_URL);
      this.models = response.data.data || [];
      
      console.log(`Found ${this.models.length} total models`);
      return this.models;
    } catch (error) {
      console.error('Error fetching models from OpenRouter:', error.message);
      throw error;
    }
  }

  /**
   * Filter models to only include chat/completion models
   */
  filterModels() {
    console.log('Filtering models...');
    
    // Debug: Count image models before filtering
    const imageModelsBefore = this.models.filter(m => 
      m.architecture?.output_modalities?.includes('image')
    );
    console.log(`Found ${imageModelsBefore.length} models with image output modality before filtering`);
    if (imageModelsBefore.length > 0) {
      console.log('Sample image models:', imageModelsBefore.slice(0, 3).map(m => ({
        id: m.id,
        provider: m.id.split('/')[0],
        output_modalities: m.architecture?.output_modalities,
        context_length: m.context_length
      })));
    }
    
    const filtered = this.models.filter(model => {
      const modelId = model.id.toLowerCase();
      const provider = model.id.split('/')[0].toLowerCase();
      
      // Check if provider is configured and enabled
      const providerConfig = this.config.providers[provider];
      if (!providerConfig || !providerConfig.enabled) {
        // Debug image models that are filtered out
        if (model.architecture?.output_modalities?.includes('image')) {
          console.log(`  Image model filtered (provider disabled/not found): ${model.id} (provider: ${provider})`);
        }
        return false;
      }
      
      // Model filtering within provider
      if (providerConfig.models.filter === 'specific') {
        if (!providerConfig.models.specific_models.includes(model.id)) {
          return false;
        }
      }
      
      // Pattern filtering within provider
      if (providerConfig.models.exclude_patterns) {
        for (const pattern of providerConfig.models.exclude_patterns) {
          if (this.matchesPattern(model.id, pattern)) {
            return false;
          }
        }
      }
      
      // Include patterns within provider (if any are specified)
      if (providerConfig.models.include_patterns && providerConfig.models.include_patterns.length > 0) {
        const matchesInclude = providerConfig.models.include_patterns.some(pattern => 
          this.matchesPattern(model.id, pattern)
        );
        if (!matchesInclude) {
          return false;
        }
      }
      
      // Filtering criteria within provider (use defaults if not specified)
      const filtering = providerConfig.filtering || {};
      const excludeModeration = filtering.exclude_moderation !== undefined ? filtering.exclude_moderation : true;
      const excludeEmbedding = filtering.exclude_embedding !== undefined ? filtering.exclude_embedding : true;
      const excludeVisionOnly = filtering.exclude_vision_only !== undefined ? filtering.exclude_vision_only : false;
      const excludeDeprecated = filtering.exclude_deprecated !== undefined ? filtering.exclude_deprecated : true;
      
      if (excludeModeration && modelId.includes('moderation')) {
        return false;
      }
      
      if (excludeEmbedding && modelId.includes('embedding')) {
        return false;
      }
      
      if (excludeVisionOnly && modelId.includes('vision')) {
        return false;
      }
      
      if (excludeDeprecated && model.deprecated) {
        return false;
      }
      
      // Context length filtering within provider
      if (filtering.min_context_length > 0 && 
          model.context_length < filtering.min_context_length) {
        return false;
      }
      
      if (filtering.max_context_length && 
          model.context_length > filtering.max_context_length) {
        return false;
      }

      // Must have text output modality (image models also have text)
      if (!model.architecture?.output_modalities?.includes('text')) {
        return false;
      }

      // Check if image generation models should be included
      const includeImageGen = this.config.generation?.include_image_generation !== false; // default true
      if (!includeImageGen && this.hasImageGenerationCapability(model)) {
        return false;
      }

      // Must have a context length (provider-specific min/max already checked above)
      // if (!model.context_length) {
      //   return false;
      // }

      return true;
    });

    // Debug: Count image models after filtering
    const imageModelsAfter = filtered.filter(m => 
      m.architecture?.output_modalities?.includes('image')
    );
    console.log(`Filtered to ${filtered.length} chat/completion models`);
    console.log(`  Including ${imageModelsAfter.length} image generation models`);
    if (imageModelsAfter.length > 0) {
      console.log('Image generation models:', imageModelsAfter.map(m => m.id));
    }
    
    this.models = filtered;
    return filtered;
  }

  /**
   * Check if a model ID matches a pattern
   */
  matchesPattern(modelId, pattern) {
    // Convert glob pattern to regex
    const regexPattern = pattern
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.')
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    
    const regex = new RegExp(regexPattern, 'i');
    return regex.test(modelId);
  }

  /**
   * Generate node name from model ID
   */
  generateNodeName(modelId) {
    // Convert model ID to kebab-case
    return modelId
      .replace(/[^a-zA-Z0-9]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase();
  }

  /**
   * Determine if model supports chat (messages) or completion (prompt)
   */
  isChatModel(model) {
    // For image generation models, be more conservative
    // Many image models are completion-based (prompt) rather than chat-based (messages)
    if (this.hasImageGenerationCapability(model)) {
      // Only treat as chat if it explicitly supports tools (strong indicator of chat capability)
      // or has a clear chat instruct_type (not null and not 'completion')
      const hasTools = model.supported_parameters?.includes('tools');
      const instructType = model.architecture?.instruct_type;
      const hasChatInstructType = instructType !== null && 
                                   instructType !== undefined && 
                                   instructType !== 'completion';
      
      // Default to completion (prompt) for image models unless clearly chat-based
      return hasTools || hasChatInstructType;
    }
    
    // For regular models, check if model supports tools (indicates chat capability)
    return model.supported_parameters?.includes('tools') || 
           model.architecture?.instruct_type !== null;
  }

  /**
   * Check if model has image generation capability
   */
  hasImageGenerationCapability(model) {
    // Check if model has image in output_modalities
    return model.architecture?.output_modalities?.includes('image') || false;
  }

  /**
   * Check if model has web search capability
   */
  hasWebSearchCapability(model) {
    // Check for web search related parameters or model names
    return model.supported_parameters?.includes('web_search_options') ||
           model.supported_parameters?.includes('search') ||
           model.id?.includes('sonar') ||
           model.id?.includes('search') ||
           model.id?.includes('web') ||
           model.name?.toLowerCase().includes('search') ||
           model.name?.toLowerCase().includes('web');
  }

  /**
   * Sort inputs with priority order: primary inputs first, then alphabetical, then by type
   */
  sortInputs(inputs) {
    const priorityInputs = ['system_prompt', 'messages', 'prompt', 'modalities', 'image_config', 'tools'];
    
    return inputs.sort((a, b) => {
      // First, sort by priority
      const aPriority = priorityInputs.indexOf(a.name);
      const bPriority = priorityInputs.indexOf(b.name);
      
      if (aPriority !== -1 && bPriority !== -1) {
        return aPriority - bPriority;
      }
      if (aPriority !== -1) return -1;
      if (bPriority !== -1) return 1;
      
      // Then alphabetical by name
      const nameCompare = a.name.localeCompare(b.name);
      if (nameCompare !== 0) return nameCompare;
      
      // Finally by type
      return a.type.localeCompare(b.type);
    });
  }

  /**
   * Sort outputs with priority order: primary outputs first, then alphabetical, then by type
   */
  sortOutputs(outputs) {
    const priorityOutputs = ['conversation', 'content', 'message', 'role', 'images', 'tool_calls', 'usage', 'cost_total', 'cost_itemized'];
    
    return outputs.sort((a, b) => {
      // First, sort by priority
      const aPriority = priorityOutputs.indexOf(a.name);
      const bPriority = priorityOutputs.indexOf(b.name);
      
      if (aPriority !== -1 && bPriority !== -1) {
        return aPriority - bPriority;
      }
      if (aPriority !== -1) return -1;
      if (bPriority !== -1) return 1;
      
      // Then alphabetical by name
      const nameCompare = a.name.localeCompare(b.name);
      if (nameCompare !== 0) return nameCompare;
      
      // Finally by type
      return a.type.localeCompare(b.type);
    });
  }

  /**
   * Generate inputs based on model capabilities
   */
  generateInputs(model) {
    const inputs = [];
    const supportedParams = model.supported_parameters || [];
    const mutedInputs = this.config.muted_inputs || [];

    // Add primary input based on model type
    if (this.isChatModel(model)) {
      inputs.push({
        name: "system_prompt",
        display_name: "System Prompt",
        type: "string or message",
        description: "System prompt to instruct the model",
        default: null
      });
      
      inputs.push({
        name: "messages",
        display_name: "Conversation", 
        type: "conversation or message or string",
        description: "Array of chat messages that make up the conversation",
        required: true
      });
    } else {
      inputs.push({
        name: "prompt",
        display_name: "Prompt",
        type: "string",
        description: "Text prompt for completion",
        required: true
      });
    }

    // Add image generation inputs if model supports image generation
    if (this.hasImageGenerationCapability(model)) {
      inputs.push({
        name: "modalities",
        display_name: "Modalities",
        type: "array",
        description: "Output modalities to request (e.g., [\"image\", \"text\"])",
        default: ["image", "text"]
      });
      
      // Check if model supports image_config (Gemini models)
      if (model.id.toLowerCase().includes('gemini') || model.id.toLowerCase().includes('nano-banana')) {
        inputs.push({
          name: "image_config",
          display_name: "Image Config",
          type: "object",
          description: "Image generation configuration (aspect_ratio: \"1:1\", \"16:9\", etc.)",
          default: null
        });
      }
    }

    // Parameters that don't make sense for image generation models
    const imageGenExcludedParams = [
      'stop',              // Stop sequences don't apply to images
      'frequency_penalty', // Text generation parameter
      'presence_penalty',  // Text generation parameter
      'max_tokens',        // Images aren't measured in tokens
      'structured_outputs' // Not relevant for image generation
    ];

    // Add supported parameters as inputs (excluding muted ones and image-gen incompatible ones)
    for (const param of supportedParams) {
      // Skip if this parameter is muted
      if (mutedInputs.includes(param)) {
        continue;
      }
      
      // Skip parameters that don't make sense for image generation
      if (this.hasImageGenerationCapability(model) && imageGenExcludedParams.includes(param)) {
        continue;
      }
      
      const mapping = PARAMETER_MAPPINGS[param];
      if (mapping) {
        inputs.push({
          name: param,
          display_name: mapping.display_name || param.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          type: mapping.type,
          description: mapping.description,
          default: mapping.default,
          ...(mapping.allow_multiple && { allow_multiple: mapping.allow_multiple })
        });
      }
    }

    return this.sortInputs(inputs);
  }

  /**
   * Generate outputs for the model
   */
  generateOutputs(model) {
    const outputs = [];
    const mutedOutputs = this.config.muted_outputs || [];

    if (this.isChatModel(model)) {
      outputs.push(
        {
          name: "conversation",
          display_name: "Conversation",
          type: "conversation",
          can_stream: true,
          description: "An array of messages including any tool call & response messages as well as the final generated output."
        },
        {
          name: "message",
          display_name: "Final Message",
          type: "message",
          can_stream: true,
          description: "The final generated response message."
        },
        {
          name: "content",
          display_name: "Content",
          can_stream: true,
          type: "string",
          description: "The content portion of the final generated response message."
        },
        {
          name: "role",
          display_name: "Role",
          can_stream: true,
          type: "string",
          description: "Role of the response (usually 'assistant')"
        }
      );

      // Add tool-related outputs if supported
      if (model.supported_parameters?.includes('tools')) {
        outputs.push({
          name: "tool_calls",
          display_name: "Tool Calls",
          type: "array of tools",
          description: "Tool calls made by the model"
        });
      }

      // Add image generation outputs if model supports image generation
      if (this.hasImageGenerationCapability(model)) {
        outputs.push({
          name: "images",
          display_name: "Images",
          type: "array",
          description: "Array of generated images (base64-encoded data URLs)"
        });
      }
    } else {
      outputs.push({
        name: "content",
        display_name: "Content",
        can_stream: true,
        type: "string",
        description: "The generated completion text"
      });

      // Add image generation outputs for completion models if supported
      if (this.hasImageGenerationCapability(model)) {
        outputs.push({
          name: "images",
          display_name: "Images",
          type: "array",
          description: "Array of generated images (base64-encoded data URLs)"
        });
      }
    }

    // Add reasoning-related outputs if supported
    if (model.supported_parameters?.includes('reasoning') || 
        model.supported_parameters?.includes('include_reasoning')) {
      outputs.push(
        {
          name: "reasoning",
          display_name: "Reasoning",
          type: "string",
          can_stream: true,
          description: "The detailed reasoning chain from the model"
        },
        {
          name: "refusal",
          display_name: "Refusal",
          type: "string",
          description: "Model refusal response (if any)"
        }
      );
    }

    // Add citation-related outputs for models that support web search
    if (this.hasWebSearchCapability(model)) {
      outputs.push(
        {
          name: "annotations",
          display_name: "Annotations",
          type: "array",
          description: "Array of annotations and citations from the response"
        },
        {
          name: "citations",
          display_name: "Citations",
          type: "array",
          description: "Array of citation URLs used by the model"
        }
      );
    }

    // Add logprobs output if supported
    if (model.supported_parameters?.includes('logprobs')) {
      outputs.push({
        name: "logprobs",
        display_name: "Log Probabilities",
        type: "object",
        description: "Token probabilities and logprobs from the model"
      });
    }

    // Common outputs
    outputs.push(
      {
        name: "finish_reason",
        display_name: "Finish Reason",
        type: "string",
        description: "Why the completion finished"
      },
      {
        name: "usage",
        display_name: "Token Usage",
        type: "object",
        description: "Token usage statistics"
      },
      {
        name: "cost_total",
        display_name: "Total Cost",
        type: "number",
        description: "Total cost for processing this request (USD)"
      },
      {
        name: "cost_itemized",
        display_name: "Itemized Cost",
        type: "array",
        description: "Detailed breakdown of costs"
      }
    );

    // Filter out muted outputs
    const filteredOutputs = outputs.filter(output => !mutedOutputs.includes(output.name));

    return this.sortOutputs(filteredOutputs);
  }

  /**
   * Generate pricing information
   */
  generatePricing(model) {
    const pricing = model.pricing || {};
    
    return {
      reference: "https://openrouter.ai/models",
      items: [
        {
          key: "input_cost_per_million",
          label: "Input Tokens (per 1M)",
          cost: parseFloat(pricing.prompt || "0") * 1_000_000,
          currency: "USD"
        },
        {
          key: "output_cost_per_million", 
          label: "Output Tokens (per 1M)",
          cost: parseFloat(pricing.completion || "0") * 1_000_000,
          currency: "USD"
        }
      ]
    };
  }

  /**
   * Generate config.json content
   */
  generateConfig(model) {
    const nodeName = this.generateNodeName(model.id);
    const isChat = this.isChatModel(model);
    const provider = model.id.split('/')[0].toLowerCase();
    const needs_key_from = ['openrouter'];

    return {
      display_name: model.name,
      description: model.description || `Chat completion using ${model.name}`,
      category: this.config.generation.category,
      provider: provider,
      accepts_plugins: model.supported_parameters?.includes('tools') || false,
      model_id: model.id,
      context_length: model.context_length,
      supported_parameters: model.supported_parameters || [],
      inputs: this.generateInputs(model),
      outputs: this.generateOutputs(model),
      pricing: this.generatePricing(model),
      // needs_key_from: needs_key_from
    };
  }

  /**
   * Generate JavaScript process file
   */
  generateJSProcess(model) {
    const nodeName = this.generateNodeName(model.id);
    const isChat = this.isChatModel(model);
    const modelId = model.id;

    const chatProcessing = this.generateChatMessageProcessing();
    const completionProcessing = this.generateCompletionProcessing();
    const conversationBuilding = this.generateConversationBuildingLogic();
    const returnValues = this.generateReturnValues(model);

    return `export default async ({inputs, settings, config, nodeConfig}) => {
    try {
        // Get OpenRouter integration from engine
        const openrouter = config.integrations?.openrouter;
        if (!openrouter) {
            throw new Error("OpenRouter integration not found");
        }

        ${isChat ? chatProcessing : completionProcessing}

        // Build parameters object from config inputs
        const params = {};
        const configInputs = ${JSON.stringify(this.generateInputs(model))};
        
        for (const input of configInputs) {

            if(input.name === 'messages') continue;

            const value = inputs[input.name];
            if (value !== null && value !== undefined) {
                params[input.name] = value;
            }
        }

        ${this.hasImageGenerationCapability(model) ? `// Set default modalities for image generation if not provided
        if (!params.modalities) {
            params.modalities = ["image", "text"];
        }` : ''}

        const response = await openrouter.chatCompletion({
            model: "${modelId}",
            ${isChat ? 'messages: messages,' : 'prompt: inputs.prompt,'}
            ...params
        }, nodeConfig, config);

        ${isChat ? conversationBuilding : ''}

        return {
            ${returnValues}
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
    const nodeName = this.generateNodeName(model.id);
    const isChat = this.isChatModel(model);
    const modelId = model.id;

    const chatProcessing = this.generatePythonChatMessageProcessing();
    const completionProcessing = this.generatePythonCompletionProcessing();
    const conversationBuilding = this.generatePythonConversationBuildingLogic();
    const returnValues = this.generatePythonReturnValues(model);

    return `async def process({inputs, settings, config, nodeConfig}):
    """Process function for the ${model.name} node"""
    try:
        # Get OpenRouter integration from engine
        openrouter = config.get("integrations", {}).get("openrouter")
        if not openrouter:
            raise Exception("OpenRouter integration not found")

        ${isChat ? chatProcessing : completionProcessing}

        # Build parameters dict from config inputs
        params = {}
        config_inputs = ${JSON.stringify(this.generateInputs(model))}
        
        for input_def in config_inputs:
            value = inputs.get(input_def["name"])
            if value is not None:
                params[input_def["name"]] = value

        ${this.hasImageGenerationCapability(model) ? `# Set default modalities for image generation if not provided
        if "modalities" not in params:
            params["modalities"] = ["image", "text"]` : ''}

        response = await openrouter.chat_completion(
            model="${modelId}",
            ${isChat ? 'messages=messages,' : 'prompt=inputs.get("prompt"),'}
            **params,
            nodeConfig=nodeConfig,
            engineConfig=config
        )

        ${isChat ? conversationBuilding : ''}

        return {
            ${returnValues}
            "cost_total": response.get("cost_total"),
            "cost_itemized": response.get("cost_itemized")
        }
    except Exception as e:
        raise Exception(f"${model.name} node error: {str(e)}")`;
  }

  /**
   * Generate chat message processing for JS
   */
  generateChatMessageProcessing() {
    return `let messages = inputs.messages;

        if(typeof messages === 'string') {
            messages = [{ role: 'user', content: messages }];
        }

        if(typeof messages === 'object' && !Array.isArray(messages)) {
            messages = [messages];
        }

        if(inputs.system_prompt) {  
            let systemPrompt = inputs.system_prompt;
            if(typeof systemPrompt === 'string') {
                systemPrompt = { role: 'system', content: systemPrompt };
            }
            messages = [systemPrompt, ...messages];
        }`;
  }

  /**
   * Generate completion processing for JS
   */
  generateCompletionProcessing() {
    return `// No message processing needed for completion models`;
  }

  /**
   * Generate parameter mapping for JS
   */
  generateParameterMapping() {
    return `// Build parameters object with only set values
            const params = {};
            
            // Add parameters that have values (not null/undefined)
            if (inputs.temperature !== null && inputs.temperature !== undefined) params.temperature = inputs.temperature;
            if (inputs.top_p !== null && inputs.top_p !== undefined) params.top_p = inputs.top_p;
            if (inputs.max_tokens !== null && inputs.max_tokens !== undefined) params.max_tokens = inputs.max_tokens;
            if (inputs.frequency_penalty !== null && inputs.frequency_penalty !== undefined) params.frequency_penalty = inputs.frequency_penalty;
            if (inputs.presence_penalty !== null && inputs.presence_penalty !== undefined) params.presence_penalty = inputs.presence_penalty;
            if (inputs.stop !== null && inputs.stop !== undefined) params.stop = inputs.stop;
            if (inputs.seed !== null && inputs.seed !== undefined) params.seed = inputs.seed;
            if (inputs.tools !== null && inputs.tools !== undefined) params.tools = inputs.tools;
            if (inputs.tool_choice !== null && inputs.tool_choice !== undefined) params.tool_choice = inputs.tool_choice;
            if (inputs.response_format !== null && inputs.response_format !== undefined) params.response_format = inputs.response_format;
            if (inputs.reasoning !== null && inputs.reasoning !== undefined) params.reasoning = inputs.reasoning;
            if (inputs.include_reasoning !== null && inputs.include_reasoning !== undefined) params.include_reasoning = inputs.include_reasoning;
            if (inputs.structured_outputs !== null && inputs.structured_outputs !== undefined) params.structured_outputs = inputs.structured_outputs;
            
            // Spread the parameters object`;
  }

  /**
   * Generate conversation building logic for JS
   */
  generateConversationBuildingLogic() {
    return `// Build conversation output: slice from end of input messages until we hit a non-tool message without tool_calls
        let conversationMessages = [];
        if (Array.isArray(messages) && messages.length > 0) {
            // Work backwards from the end
            for (let i = messages.length - 1; i >= 0; i--) {
                const msg = messages[i];
                if (!msg || typeof msg !== 'object') continue;
                
                const isTool = msg.role === 'tool';
                const hasToolCalls = msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0;
                
                // Include this message if it's a tool message or has tool_calls
                if (isTool || hasToolCalls) {
                    conversationMessages.unshift(msg);
                } else {
                    // Stop when we hit a message that is not tool and has no tool_calls
                    break;
                }
            }
        }
        
        // Append the final output message
        const finalMessage = {
            content: response.content,
            role: response.role
        };
        if (response.tool_calls) {
            finalMessage.tool_calls = response.tool_calls;
        }
        if (response.images) {
            finalMessage.images = response.images;
        }
        conversationMessages.push(finalMessage);
        
        const conversation = conversationMessages;`;
  }

  /**
   * Generate conversation building logic for Python
   */
  generatePythonConversationBuildingLogic() {
    return `# Build conversation output: slice from end of input messages until we hit a non-tool message without tool_calls
        conversation_messages = []
        if isinstance(messages, list) and len(messages) > 0:
            # Work backwards from the end
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if not isinstance(msg, dict):
                    continue
                
                is_tool = msg.get("role") == "tool"
                has_tool_calls = msg.get("tool_calls") and isinstance(msg.get("tool_calls"), list) and len(msg.get("tool_calls", [])) > 0
                
                # Include this message if it's a tool message or has tool_calls
                if is_tool or has_tool_calls:
                    conversation_messages.insert(0, msg)
                else:
                    # Stop when we hit a message that is not tool and has no tool_calls
                    # Include this message as the starting point
                    conversation_messages.insert(0, msg)
                    break
        
        # Append the final output message
        final_message = {
            "content": response.get("content"),
            "role": response.get("role")
        }
        if response.get("tool_calls"):
            final_message["tool_calls"] = response.get("tool_calls")
        if response.get("images"):
            final_message["images"] = response.get("images")
        conversation_messages.append(final_message)
        
        conversation = conversation_messages`;
  }

  /**
   * Generate return values for JS
   */
  generateReturnValues(model) {
    const isChat = this.isChatModel(model);
    const hasReasoning = model.supported_parameters?.includes('reasoning') || 
                        model.supported_parameters?.includes('include_reasoning');
    const hasWebSearch = this.hasWebSearchCapability(model);
    const hasLogprobs = model.supported_parameters?.includes('logprobs');
    const hasImageGen = this.hasImageGenerationCapability(model);
    
    let returnValues = '';
    
    if (isChat) {
      returnValues += `conversation: conversation,
            message: {
                content: response.content,
                role: response.role,
                tool_calls: response.tool_calls
            },
            content: response.content,
            role: response.role,
            tool_calls: response.tool_calls,`;
    } else {
      returnValues += `content: response.content,`;
    }

    // Add images output if model supports image generation
    if (hasImageGen) {
      returnValues += `
            images: response.images,`;
    }

    // Add reasoning-related outputs
    if (hasReasoning) {
      returnValues += `
            reasoning: response.reasoning,
            refusal: response.refusal,`;
    }

    // Add web search outputs
    if (hasWebSearch) {
      returnValues += `
            annotations: response.annotations,
            citations: response.citations,`;
    }

    // Add logprobs output
    if (hasLogprobs) {
      returnValues += `
            logprobs: response.logprobs,`;
    }

    // Common outputs
    returnValues += `
            finish_reason: response.finish_reason,
            usage: response.usage,`;

    return returnValues;
  }

  /**
   * Generate Python chat message processing
   */
  generatePythonChatMessageProcessing() {
    return `messages = inputs.get("messages", [])

        if isinstance(messages, str):
            messages = [{ "role": "user", "content": messages }]

        if isinstance(messages, dict):
            messages = [messages]

        if inputs.get("system_prompt"):
            system_prompt = inputs.get("system_prompt") 
            if isinstance(system_prompt, str):
                system_prompt = {"role": "system", "content": system_prompt}

            messages = [system_prompt, *messages]`;
  }

  /**
   * Generate Python completion processing
   */
  generatePythonCompletionProcessing() {
    return `# No message processing needed for completion models`;
  }

  /**
   * Generate Python parameter mapping
   */
  generatePythonParameterMapping() {
    return `# Build parameters dict with only set values
            params = {}
            
            # Add parameters that have values (not None)
            if inputs.get("temperature") is not None: params["temperature"] = inputs.get("temperature")
            if inputs.get("top_p") is not None: params["top_p"] = inputs.get("top_p")
            if inputs.get("max_tokens") is not None: params["max_tokens"] = inputs.get("max_tokens")
            if inputs.get("frequency_penalty") is not None: params["frequency_penalty"] = inputs.get("frequency_penalty")
            if inputs.get("presence_penalty") is not None: params["presence_penalty"] = inputs.get("presence_penalty")
            if inputs.get("stop") is not None: params["stop"] = inputs.get("stop")
            if inputs.get("seed") is not None: params["seed"] = inputs.get("seed")
            if inputs.get("tools") is not None: params["tools"] = inputs.get("tools")
            if inputs.get("tool_choice") is not None: params["tool_choice"] = inputs.get("tool_choice")
            if inputs.get("response_format") is not None: params["response_format"] = inputs.get("response_format")
            if inputs.get("reasoning") is not None: params["reasoning"] = inputs.get("reasoning")
            if inputs.get("include_reasoning") is not None: params["include_reasoning"] = inputs.get("include_reasoning")
            if inputs.get("structured_outputs") is not None: params["structured_outputs"] = inputs.get("structured_outputs")
            
            # Spread the parameters dict`;
  }

  /**
   * Generate Python return values
   */
  generatePythonReturnValues(model) {
    const isChat = this.isChatModel(model);
    const hasReasoning = model.supported_parameters?.includes('reasoning') || 
                        model.supported_parameters?.includes('include_reasoning');
    const hasWebSearch = this.hasWebSearchCapability(model);
    const hasLogprobs = model.supported_parameters?.includes('logprobs');
    const hasImageGen = this.hasImageGenerationCapability(model);
    
    let returnValues = '';
    
    if (isChat) {
      returnValues += `"conversation": conversation,
            "message": {
                "content": response["content"],
                "role": response["role"],
                "tool_calls": response.get("tool_calls")
            },
            "content": response["content"],
            "role": response["role"],
            "tool_calls": response.get("tool_calls"),`;
    } else {
      returnValues += `"content": response["content"],`;
    }

    // Add images output if model supports image generation
    if (hasImageGen) {
      returnValues += `
            "images": response.get("images"),`;
    }

    // Add reasoning-related outputs
    if (hasReasoning) {
      returnValues += `
            "reasoning": response.get("reasoning"),
            "refusal": response.get("refusal"),`;
    }

    // Add web search outputs
    if (hasWebSearch) {
      returnValues += `
            "annotations": response.get("annotations"),
            "citations": response.get("citations"),`;
    }

    // Add logprobs output
    if (hasLogprobs) {
      returnValues += `
            "logprobs": response.get("logprobs"),`;
    }

    // Common outputs
    returnValues += `
            "finish_reason": response["finish_reason"],
            "usage": response["usage"]`;

    return returnValues;
  }

  /**
   * Generate test file
   */
  generateTests(model) {
    const nodeName = this.generateNodeName(model.id);
    const isChat = this.isChatModel(model);
    
    const tests = [
      {
        description: `Basic ${isChat ? 'chat' : 'completion'} with default settings`,
        inputs: isChat ? {
          messages: [{ role: "user", content: "Hello, how are you?" }]
        } : {
          prompt: "Hello, how are you?"
        },
        expectedSchema: {
          content: {
            type: "string"
          },
          finish_reason: {
            type: "string"
          },
          usage: {
            type: "object"
          },
          cost_total: {
            type: "number",
            minimum: 0
          },
          cost_itemized: {
            type: "array"
          }
        }
      }
    ];

    if (isChat) {
      tests.push({
        description: "Chat with system prompt",
        inputs: {
          system_prompt: "You are a helpful assistant.",
          messages: [{ role: "user", content: "What is 2+2?" }]
        },
        expectedSchema: {
          content: {
            type: "string"
          },
          role: {
            type: "string"
          },
          finish_reason: {
            type: "string"
          },
          usage: {
            type: "object"
          }
        }
      });
    }

    if (model.supported_parameters?.includes('temperature')) {
      tests.push({
        description: "With custom temperature",
        inputs: {
          ...(isChat ? { messages: [{ role: "user", content: "Hello" }] } : { prompt: "Hello" }),
          temperature: 0.5
        },
        expectedSchema: {
          content: {
            type: "string"
          },
          finish_reason: {
            type: "string"
          },
          usage: {
            type: "object"
          }
        }
      });
    }

    return tests;
  }


  /**
   * Generate a single node
   */
  generateNode(model) {
    const nodeName = this.generateNodeName(model.id);
    const nodeDir = path.join(NODES_DIR, nodeName);
    
    console.log(`Generating node: ${nodeName}`);

    // Create node directory
    if (!this.options.dryRun) {
      if (fs.existsSync(nodeDir)) {
        fs.rmSync(nodeDir, { recursive: true });
      }
      fs.mkdirSync(nodeDir, { recursive: true });
    }

    // Generate files
    const config = this.generateConfig(model);
    const jsProcess = this.generateJSProcess(model);
    const pythonProcess = this.generatePythonProcess(model);
    const tests = this.generateTests(model);

    const files = [
      {
        path: path.join(nodeDir, `${nodeName}.config.json`),
        content: JSON.stringify(config, null, 2)
      },
      {
        path: path.join(nodeDir, `${nodeName}.process.js`),
        content: jsProcess
      },
      {
        path: path.join(nodeDir, `${nodeName}.process.py`),
        content: pythonProcess
      },
      {
        path: path.join(nodeDir, `${nodeName}.tests.json`),
        content: JSON.stringify(tests, null, 2)
      }
    ];

    // Write files
    for (const file of files) {
      if (!this.options.dryRun) {
        fs.writeFileSync(file.path, file.content);
        console.log(`  Created: ${path.relative(BASE_DIR, file.path)}`);
      } else {
        console.log(`  Would create: ${path.relative(BASE_DIR, file.path)}`);
      }
    }

    this.generatedNodes.push({
      name: nodeName,
      model: model.id,
      config: config
    });
  }


  /**
   * Remove existing LLM nodes
   */
  /**
   * Get all existing LLM nodes in the nodes directory
   */
  getExistingLLMNodes() {
    const existingNodes = [];
    
    if (!fs.existsSync(NODES_DIR)) {
      return existingNodes;
    }
    
    const nodeDirs = fs.readdirSync(NODES_DIR, { withFileTypes: true });
    
    for (const dirent of nodeDirs) {
      if (dirent.isDirectory()) {
        const nodeName = dirent.name;
        const configPath = path.join(NODES_DIR, nodeName, `${nodeName}.config.json`);
        
        // Check if this is an LLM node by looking for the config file and checking category
        if (fs.existsSync(configPath)) {
          try {
            const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            if (config.category === 'llm') {
              existingNodes.push(nodeName);
            }
          } catch (error) {
            // If we can't read the config, skip this node
            console.warn(`Warning: Could not read config for ${nodeName}: ${error.message}`);
          }
        }
      }
    }
    
    return existingNodes;
  }

  /**
   * Remove existing LLM nodes when overwrite_existing is enabled
   */
  removeExistingLLMNodes() {
    const existingLLMNodes = this.getExistingLLMNodes();
    const generatedNodeNames = this.models.map(model => this.generateNodeName(model.id));
    
    console.log(`Found ${existingLLMNodes.length} existing LLM nodes`);
    console.log(`Will generate ${generatedNodeNames.length} new LLM nodes`);
    
    for (const nodeName of existingLLMNodes) {
      const nodeDir = path.join(NODES_DIR, nodeName);
      if (fs.existsSync(nodeDir)) {
        if (!this.options.dryRun) {
          fs.rmSync(nodeDir, { recursive: true });
          console.log(`Removed existing LLM node: ${nodeName}`);
        } else {
          console.log(`Would remove existing LLM node: ${nodeName}`);
        }
      }
    }
  }

  /**
   * Main generation process
   */
  async generate() {
    console.log('Starting LLM node generation...\n');

    // Fetch and filter models
    await this.fetchModels();
    const filteredModels = this.filterModels();

    // Remove existing LLM nodes if cleanup is enabled
    if (this.config.output.cleanup_old_nodes) {
      this.removeExistingLLMNodes();
    } else {
      console.log('Skipping cleanup of old LLM nodes (cleanup_old_nodes: false)');
    }

    // Generate nodes for each model
    for (const model of filteredModels) {
      try {
        this.generateNode(model);
      } catch (error) {
        console.error(`Error generating node for ${model.id}:`, error.message);
      }
    }

    console.log(`\nGeneration complete! Generated ${this.generatedNodes.length} LLM nodes.`);
    
    if (this.options.dryRun) {
      console.log('This was a dry run. No files were actually created.');
    } else {
      console.log('Run the sync script to update engine directories:');
      console.log('cd scripts && python sync_nodes.py');
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
    baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1',
    referer: process.env.OPENROUTER_REFERER || 'https://zerowidth.ai',
    title: process.env.OPENROUTER_TITLE || 'ZeroWidth SDK'
  };

  if (!options.apiKey) {
    console.error('Error: OPENROUTER_API_KEY environment variable is required');
    console.error('Create a .env file in the scripts directory with:');
    console.error('OPENROUTER_API_KEY=your_api_key_here');
    console.error('');
    console.error('Or set it as an environment variable:');
    console.error('export OPENROUTER_API_KEY=your_key_here');
    process.exit(1);
  }

  console.log('Using configuration:', JSON.stringify(config, null, 2));

  const generator = new LLMNodeGenerator(options);
  
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

module.exports = LLMNodeGenerator; 