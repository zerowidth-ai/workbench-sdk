# Node Development Guidelines

This document outlines the standards and best practices for developing nodes in the zv1 framework. Following these guidelines ensures consistency, maintainability, and proper integration with the zv1 execution engine.

## Table of Contents

- [File Structure](#file-structure)
- [Naming Conventions](#naming-conventions)
- [Configuration Files](#configuration-files)
- [Process Files](#process-files)
- [Error Handling](#error-handling)
- [Integration Usage](#integration-usage)
- [Plugin vs Standard Nodes](#plugin-vs-standard-nodes)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Standards](#documentation-standards)

## File Structure

Each node must have the following files in its directory:

```
nodes/your-node-name/
├── your-node-name.config.json    # Node configuration and schema
├── your-node-name.process.js     # Node execution logic
└── your-node-name.tests.json     # Test cases (optional but recommended)
```

## Naming Conventions

### Directory and File Names
- **Directory name**: Use kebab-case (e.g., `newsdata-io-latest`, `openai-gpt-4`)
- **File names**: Match the directory name exactly
- **Node type**: Same as directory name (used in flow definitions)

### Input/Output/Setting Names
- **Use snake_case**: `total_results`, `next_page`, `api_key`
- **Be descriptive**: `exclude_categories` not `exclude_cats`
- **Use consistent terminology**: `total_results` across all similar nodes

### Display Names
- **Use Title Case**: "Total Results", "Next Page Token", "API Key"
- **Be user-friendly**: "Search Query" not "Query String"
- **Match the functionality**: "Articles" for news data, "Sources" for domain lists

### Examples

```json
{
  "name": "total_results",           // snake_case
  "display_name": "Total Results",   // Title Case
  "type": "number"
}
```

## Configuration Files

### Required Fields

```json
{
  "display_name": "Node Display Name",
  "description": "Clear description of what this node does",
  "category": "ai|data|logic|io|third-party|testing",
  "provider": "service_name_or_framework",
  "needs_key_from": ["service_name"],
  "is_plugin": true|false,
  "inputs": [...],
  "outputs": [...],
  "settings": [...]
}
```

### Category Guidelines

- **`ai`**: AI models, LLMs, embeddings, vector operations
- **`data`**: Data processing, transformation, parsing
- **`logic`**: Conditionals, loops, control flow
- **`io`**: Input/output, file operations, user interaction
- **`third-party`**: External API integrations
- **`testing`**: Test utilities, error simulation

### Input/Output Definitions

#### Input Fields
```json
{
  "name": "field_name",                    // snake_case
  "display_name": "Field Display Name",    // Title Case
  "type": "string|number|boolean|array|object",
  "description": "Clear description of what this input does",
  "required": true|false,                  // optional, defaults to false
  "default": "default_value",              // optional, don't ever use default: null - just remove entirely
  "options": ["option1", "option2"]        // for select/enum inputs
}
```

#### Output Fields
```json
{
  "name": "output_field",                  // snake_case
  "display_name": "Output Field Name",     // Title Case
  "type": "string|number|boolean|array of objects|array of strings",
  "description": "What this output contains"
}
```

#### Connection Suggestions

Connection suggestions provide hints for common connection patterns to improve the user experience when building flows. These are optional and purely informational - they don't affect execution.

**For Input Fields**: Suggests a source node type and its output port that commonly connects to this input.
```json
{
  "name": "key",
  "display_name": "Key",
  "type": "string",
  "description": "The name of the property to set",
  "suggestion": {
    "type": "string",
    "name": "value"
  }
}
```

**For Output Fields**: Suggests a target node type and its input port that this output commonly connects to.
```json
{
  "name": "object",
  "display_name": "Object",
  "type": "object",
  "description": "The new object with the property set",
  "suggestion": {
    "type": "set-object-property",
    "name": "object"
  }
}
```

**Guidelines**:
- Use `suggestion` only when there's a clear, common pattern (80%+ of use cases)
- Always specify both `type` (kebab-case node type) and `name` (snake_case port name)
- For inputs: `name` refers to the output port on the suggested source node
- For outputs: `name` refers to the input port on the suggested target node
- Only one suggestion per input/output field
- Omit if the connection pattern is not obvious or varies significantly
- **Primary Outputs**: If a node doesn't have any outputs marked as primary, the first non-hidden output is assumed to be the primary output

#### Type Guidelines
- **Arrays**: Use `"array of objects"` or `"array of strings"` for clarity
- **Complex types**: Be specific about what the object contains
- **Multitypes** Use the "or" to delimit multiple types and aim to handle as much translation as possible. Ex: `"string or array of strings"` and internally in the process.js function if a single string is detected, convert it to an array
- **Optional fields**: Sometimes outputs are null, this will stop propagation and can be used to make conditional routing

### Settings
- Use for node-level configuration that doesn't change per execution
- Follow same naming conventions as inputs
- Keep to a minimum - prefer inputs for user data or orchestration-defined values

## Process Files

### Function Signature
```javascript
export default async ({inputs, settings, config, nodeConfig}) => {
  // Node logic here
  return {
    output_field: value
  };
};
```

### Best Practices

#### 1. Error Handling
```javascript
// ✅ DO: Let errors bubble up to error manager
export default async ({inputs, settings, config, nodeConfig}) => {
  const integration = config.integrations?.service_name;
  if (!integration) {
    throw new Error("Service integration not found");
  }
  
  const result = await integration.someMethod(inputs);
  return { data: result };
};

// ❌ DON'T: Catch and return errors as output
export default async ({inputs, settings, config, nodeConfig}) => {
  try {
    const result = await someOperation();
    return { data: result, success: true };
  } catch (error) {
    return { data: null, success: false, error: error.message };
  }
};
```

#### 2. Input Validation
```javascript
// ✅ DO: Automagically convert input types
export default async ({inputs, settings, config, nodeConfig}) => {
  if (typeof inputs.array_of_strings_field === 'string) {
    inputs.array_of_strings_field = [inputs.array_of_strings_field]
  }

  // All required inputs and default values are handled PRIOR to the process function being called
  
  // Process inputs...
  
};
```

#### 3. Return Clean Data
```javascript
// ✅ DO: Return only the data, no status fields
return {
  articles: response.results || [],
  total_results: response.totalResults || 0,
  next_page: response.nextPage || null
};

// ❌ DON'T: Include success/status/error fields
return {
  articles: response.results || [],
  success: true,
  status: 'success',
  error: null
};
```

#### 4. Handle Optional Fields
```javascript
// ✅ DO: Use nullish coalescing for optional fields, or use null to stop propagation 
return {
  data: response.data || [],
  count: response.count ?? 0,
  metadata: response.metadata || {},
  did_thing_happen: null
};
```

## Error Handling

### Error Types
- **`node`**: Errors during node execution (most common)
- **`flow`**: Flow structure or validation errors
- **`system`**: System-level errors
- **`validation`**: Input/output validation errors
- **`timeout`**: Execution timeout errors
- **`resource`**: Resource allocation errors

### Error Messages
- Be descriptive and actionable
- Include the field name for validation errors
- Don't expose sensitive information
- Use consistent language across similar nodes

```javascript
// ✅ Good error messages
throw new Error("API key is required for this service");
throw new Error("Invalid date format. Expected YYYY-MM-DD");
throw new Error("Maximum 5 countries allowed, received 8");

// ❌ Poor error messages
throw new Error("Error");
throw new Error("Invalid input");
throw new Error("Failed");
```

## Integration Usage

### Accessing Integrations
```javascript
// Get integration from config
const integration = config.integrations?.service_name;
if (!integration) {
  throw new Error("Service integration not found");
}
// If a node requires an integration and that key isn't set, it'll already be blocked by the engine prior to the process function

// Use integration methods
const result = await integration.someMethod(params);
```

### Parameter Processing
```javascript
// Process parameters for API calls
const processedParams = integration.constructor.processParams(params);
const response = await integration.getData(processedParams);
```

### Integration Requirements
- Specify in `needs_key_from` array in config
- Use integration's built-in parameter processing when available

## Plugin vs Standard Nodes

### Plugin Nodes (`"is_plugin": true`)
- Any node that might be useful to give to an LLM as a tool
- Ideally, nearly all nodes make sense as is_plugin besides constants
- External service integrations
- Require API keys or authentication
- Examples: OpenAI, NewsData, HTTP requests

### Constant Nodes (`"is_constant": true`)
- Nodes that will be ran first to kickoff flows prior to even processing input data
- Typically building-block fundamentals: strings, numbers, etc

## Testing Guidelines

### Test File Structure
```json
{
  "test_cases": [
    {
      "name": "Basic functionality test",
      "inputs": {
        "input_field": "test_value"
      },
      "expected": {
        "output_field": "expected_result"
      }
    },
    {
      "name": "Error handling test",
      "inputs": {
        "invalid_input": "bad_value"
      },
      "expectedError": {
        "type": "node",
        "message": "Expected error message"
      }
    }
  ]
}
```

### Test Coverage
- **Happy path**: Normal operation with valid inputs
- **Edge cases**: Empty inputs, boundary values
- **Error cases**: Invalid inputs, missing required fields
- **Integration tests**: With actual service calls (use test API keys)

### Running Tests
```bash
# Test specific node
node tests/test.all-nodes.js --node your-node-name

# Test all nodes
npm run test-nodes
```

## Documentation Standards

### Node Description
- Start with action verb: "Fetch", "Process", "Transform", "Validate"
- Be specific about what the node does
- Mention key features or limitations

```json
{
  "description": "Fetch latest headlines from the last 48 hours with rich filtering options including keywords, countries, regions, categories, and more"
}
```

### Input/Output Descriptions
- Explain what the field contains
- Mention format requirements
- Include examples for complex fields
- Note limitations or constraints

```json
{
  "name": "from_date",
  "display_name": "From Date",
  "type": "string",
  "description": "Start date in YYYY-MM-DD format",
  "required": true
}
```

### Type Descriptions
- Be specific about array contents
- Mention object structure when relevant
- Use consistent terminology

```json
{
  "name": "articles",
  "display_name": "Articles",
  "type": "array of objects",
  "description": "Array of article objects with metadata including title, content, author, and publication date"
}
```

## Common Patterns

### Array Input Handling
```javascript
// Handle both string and array inputs
const arrayFields = ['countries', 'categories', 'languages'];
arrayFields.forEach(field => {
  if (inputs[field] !== null && inputs[field] !== undefined) {
    params[field] = integration.constructor.stringToArray(inputs[field]);
  }
});
```

### Parameter Mapping
```javascript
// Sometimes you might need to map input names to specific parameter names of various APIs
const paramMappings = {
  'input_name': 'api_parameter_name',
  'countries': 'country',
  'exclude_categories': 'excludecategory'
};

Object.entries(paramMappings).forEach(([inputKey, apiKey]) => {
  if (inputs[inputKey] !== null && inputs[inputKey] !== undefined) {
    params[apiKey] = inputs[inputKey];
  }
});
```


## Examples

### Complete Node Example

**Config File** (`example-node.config.json`):
```json
{
  "display_name": "Example Data Processor",
  "description": "Process and transform input data with validation and filtering",
  "category": "data",
  "provider": "internal",
  "is_plugin": false,
  "inputs": [
    {
      "name": "input_data",
      "display_name": "Input Data",
      "type": "array of objects",
      "description": "Array of data objects to process",
      "required": true
    },
    {
      "name": "filter_field",
      "display_name": "Filter Field",
      "type": "string",
      "description": "Field name to filter by",
      "suggestion": {
        "type": "string",
        "name": "value"
      }
    },
    {
      "name": "max_items",
      "display_name": "Maximum Items",
      "type": "number",
      "description": "Maximum number of items to return",
      "default": 100
    }
  ],
  "outputs": [
    {
      "name": "processed_data",
      "display_name": "Processed Data",
      "type": "array of objects",
      "description": "Filtered and processed data objects"
    },
    {
      "name": "total_count",
      "display_name": "Total Count",
      "type": "number",
      "description": "Total number of processed items"
    }
  ],
  "settings": []
}
```

**Process File** (`example-node.process.js`):
```javascript
export default async ({inputs, settings, config, nodeConfig}) => {
  // Remember, input validation has already taken place at this point

  // Process data
  let processedData = inputs.input_data;

  // Apply filter if specified
  if (inputs.filter_field) {
    processedData = processedData.filter(item => 
      item[inputs.filter_field] !== undefined && 
      item[inputs.filter_field] !== null
    );
  }

  // Apply max items limit
  const maxItems = inputs.max_items || 100;
  if (processedData.length > maxItems) {
    processedData = processedData.slice(0, maxItems);
  }

  return {
    processed_data: processedData,
    total_count: processedData.length
  };
};
```

## Macro Nodes

Macro nodes are composite nodes that contain internal flows of other nodes. They execute as self-contained mini-flows, providing a way to create reusable, higher-level functionality by combining multiple simpler nodes.

### Macro Node Structure

```json
{
  "display_name": "Read Website",
  "description": "Simple website reader - scrapes content and extracts main text",
  "category": "macro",
  "provider": "internal",
  "is_macro": true,
  "is_plugin": true,
  "macro_flow": {
    "nodes": [
      {
        "id": "input_url",
        "type": "input-data",
        "settings": {
          "key": "url"
        }
      },
      {
        "id": "formats",
        "type": "string",
        "settings": {
          "value": "markdown"
        }
      },
      {
        "id": "scrape",
        "type": "firecrawl-scrape"
      },
      {
        "id": "output_content",
        "type": "output-data",
        "settings": {
          "key": "content"
        }
      }
    ],
    "links": [
      {
        "from": { "node_id": "input_url", "port_name": "value" },
        "to": { "node_id": "scrape", "port_name": "url" }
      },
      {
        "from": { "node_id": "formats", "port_name": "value" },
        "to": { "node_id": "scrape", "port_name": "formats" }
      },
      {
        "from": { "node_id": "scrape", "port_name": "markdown" },
        "to": { "node_id": "output_content", "port_name": "value" }
      }
    ]
  },
  "inputs": [
    {
      "name": "url",
      "display_name": "Website URL",
      "type": "string",
      "description": "The website to read",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "content",
      "display_name": "Content",
      "type": "string",
      "description": "The main text content of the website"
    }
  ],
  "settings": []
}
```

### Macro Node with Plugin Support

Macros can accept plugins (tools) that will be passed to internal LLM nodes. When a plugin is connected to a macro, it executes in the parent context with all its dependencies intact, while the internal LLM only sees the clean tool schema.

```json
{
  "display_name": "AI Text Analyzer",
  "description": "Uses AI to analyze text with custom tools",
  "category": "macro",
  "provider": "internal",
  "is_macro": true,
  "is_plugin": true,
  "accepts_plugins": true,
  "macro_flow": {
    "nodes": [
      {
        "id": "input_text",
        "type": "input-data",
        "settings": {
          "key": "text"
        }
      },
      {
        "id": "llm_analyzer",
        "type": "anthropic-claude-3-5-sonnet"
      },
      {
        "id": "output_analysis",
        "type": "output-data",
        "settings": {
          "key": "analysis"
        }
      }
    ],
    "links": [
      {
        "from": { "node_id": "input_text", "port_name": "value" },
        "to": { "node_id": "llm_analyzer", "port_name": "messages" }
      },
      {
        "from": { "node_id": "llm_analyzer", "port_name": "response" },
        "to": { "node_id": "output_analysis", "port_name": "value" }
      }
    ]
  },
  "inputs": [
    {
      "name": "text",
      "display_name": "Text",
      "type": "string",
      "description": "Text to analyze",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "analysis",
      "display_name": "Analysis",
      "type": "string",
      "description": "AI analysis result"
    }
  ],
  "plugins": [
    {
      "connects_to": "llm_analyzer"
    }
  ],
  "settings": []
}
```

### Macro Node Fields

#### Required Fields
- **`is_macro`**: Must be `true` for macro nodes
- **`macro_flow`**: Object containing the internal flow with `nodes` and `links` arrays
  - Must include `input-data` nodes for each macro input
  - Must include `output-data` nodes for each macro output
- **`inputs`**: Array of input definitions (matches `input-data` nodes)
- **`outputs`**: Array of output definitions (matches `output-data` nodes)

#### Optional Fields
- **`accepts_plugins`**: Set to `true` if the macro accepts plugin connections
- **`plugins`**: Array of plugin mappings (required if `accepts_plugins` is true)
  - Each entry has `connects_to` field specifying which internal LLM node receives the plugins
  - Currently only one plugin mapping is supported (all plugins go to one internal LLM)

#### Macro Flow Structure
- **`nodes`**: Array of internal nodes including:
  - `input-data` nodes for each macro input (with `key` matching input name)
  - `output-data` nodes for each macro output (with `key` matching output name)
  - Processing nodes (regular nodes, LLMs, etc.)
- **`links`**: Array of links between internal nodes

### Macro Node Best Practices

#### 1. Keep It Simple
- Aim for 1 input, 1 output when possible
- Use descriptive names for internal nodes
- Keep the internal flow focused and easy to understand

#### 2. Input/Output Design
- Use `input-data` and `output-data` nodes to define entry/exit points
- Ensure input/output names match the `key` in the corresponding data nodes
- Use constant nodes (like `string`) for values that don't need to be configurable

#### 3. Plugin Support
- Only add `accepts_plugins` if your macro has an internal LLM that needs tools
- Specify which internal LLM node receives plugins via the `plugins` array
- All external plugins connected to the macro will go to the specified internal LLM
- The internal LLM node must have `accepts_plugins: true` in its config

#### 4. Internal Node Naming
- Use descriptive IDs for internal nodes (e.g., `input_text`, `llm_analyzer`, `output_result`)
- Prefix input/output nodes clearly (`input_*`, `output_*`)
- Make the flow self-documenting

#### 5. Error Handling
- Let errors from internal nodes bubble up naturally
- Don't add extra error handling in macro nodes
- The engine will handle errors and provide context

## Custom Tools API

The zv1 engine supports passing custom tools to LLM nodes via the configuration. This is particularly useful when you want to provide external functionality to LLMs without modifying the flow definition.

### Developer-Facing API

```javascript
const engine = await zv1.create('./myflow.zv1', {
  keys: { openai: 'sk-...' },
  tools: {
    // Full definition: schema + implementation
    'get_weather': {
      schema: {
        name: 'get_weather',
        description: 'Get current weather for a city',
        parameters: {
          type: 'object',
          properties: {
            city: { type: 'string', description: 'City name' },
            units: { type: 'string', enum: ['celsius', 'fahrenheit'] }
          },
          required: ['city']
        }
      },
      process: async (args) => {
        // Your custom tool implementation
        const weather = await fetchWeather(args.city, args.units);
        return { temperature: weather.temp, conditions: weather.conditions };
      }
    },
    
    // Process only: uses schema from flow's tool node
    'lookup_customer': {
      process: async (args) => {
        // Flow already defines the schema via a tool node
        // You just provide the implementation
        return await db.customers.findOne({ id: args.customer_id });
      }
    }
  }
});
```

### Tool Definition Structure

The `tools` config is an **object** where each key is the tool name and the value defines the tool:

- **`schema`** (Object, Optional): OpenAPI-like schema defining the tool
  - **`name`** (String): Tool name (must match the key)
  - **`description`** (String): What the tool does
  - **`parameters`** (Object): JSON Schema for tool parameters
    - **`type`**: Must be "object"
    - **`properties`**: Object defining each parameter
    - **`required`**: Array of required parameter names
  - If omitted, the engine will look for a schema defined in the flow (via tool node)

- **`process`** (Function, Required): Async function that executes the tool
  - Receives parsed arguments as a single object parameter
  - Should return an object or value to be passed back to the LLM
  - Errors should be thrown and will be handled by the engine

### Internal Usage

This API is also used internally by the engine to pass plugin functionality from parent flows to internal engines (macros and imports). When a plugin node is connected to a macro or import, the engine automatically creates tool runners that execute in the parent context.

### Best Practices

1. **Tool Names**: Use descriptive, snake_case names (e.g., `get_weather`, `search_database`)
2. **Error Handling**: Throw descriptive errors - they'll be caught and formatted properly
3. **Return Values**: Return structured data when possible, not just strings
4. **Side Effects**: Tools can have side effects (API calls, database updates, etc.)
5. **Async Operations**: All tool processes should be async functions

## Internal Events Configuration

By default, macro nodes fire only their own start/complete/error events, hiding the internal node executions. If you want to see all internal node events (for debugging or monitoring), use the `includeInternalEvents` option:

```javascript
const engine = await zv1.create('./myflow.zv1', {
  keys: { openai: 'sk-...' },
  includeInternalEvents: true,  // See internal macro/import events
  onNodeStart: (event) => {
    console.log('Node started:', event);
    // Will now see events from nodes INSIDE macros
  }
});
```

**Default behavior** (`includeInternalEvents: false`):
- Macro node fires: `onNodeStart` → `onNodeComplete`
- Internal nodes are hidden
- Clean, high-level view

**With `includeInternalEvents: true`**:
- Macro node fires: `onNodeStart`
- Each internal node fires: `onNodeStart` → `onNodeComplete`
- Macro node fires: `onNodeComplete`
- Detailed, granular view for debugging

## Checklist

Before submitting a new node, ensure:

- [ ] Directory and file names use kebab-case
- [ ] Input/output names use snake_case
- [ ] Display names use Title Case
- [ ] All required config fields are present
- [ ] Error handling throws errors instead of returning them
- [ ] No success/status/error fields in outputs
- [ ] Input validation is performed
- [ ] Descriptions are clear and helpful
- [ ] Connection suggestions added where there are clear common patterns (optional)
- [ ] Test cases cover happy path and error cases
- [ ] Integration usage follows patterns
- [ ] Code is clean and well-commented

---

Following these guidelines ensures consistency, maintainability, and proper integration with the zv1 framework. When in doubt, look at existing nodes for examples of best practices.
