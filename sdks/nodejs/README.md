# @zerowidth/workbench-sdk

A Node.js implementation of ZeroWidth's Workbench framework for executing AI and automation workflows through a visual node-based interface. Design flows on [zerowidth.ai](https://zerowidth.ai), export them, and execute with precision and control.

> **Migrating from `zv1`?** This package is the drop-in successor to the legacy `zv1` npm package. Run `npm uninstall zv1 && npm install @zerowidth/workbench-sdk`, then `import Workbench from '@zerowidth/workbench-sdk'`. The public API is unchanged.

[![Apache 2.0 License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [Nodes & Links](#nodes--links)
  - [Flow Processing](#flow-processing)
  - [Input/Output System](#inputoutput-system)
- [API Keys & Security](#api-keys--security)
- [Event Handlers](#event-handlers)
- [Error Handling](#error-handling)
- [Advanced Features](#advanced-features)
- [Testing & Development](#testing)
- [API Reference](#api-reference)
- [Examples](#examples)

## Overview

The Workbench Flow Engine enables you to:
- Execute complex AI and automation workflows
- Connect various node types (data processing, AI models, tools, testing utilities)
- Handle asynchronous operations with precision
- Monitor and debug flow execution with detailed timelines
- Integrate with external systems and APIs
- Test error handling and recovery scenarios
- Manage costs and resource usage

## Installation

```bash
npm install @zerowidth/workbench-sdk
```

Requires Node.js 20 or later. Flows that use knowledge bases (SQLite) need Node.js 22.5 or later.

## Quick Start

```javascript
import Workbench from '@zerowidth/workbench-sdk';

// Create engine instance by passing the location of your configured flow
const engine = await Workbench.create('./path/to/myflow.zwf', {
  keys: {
    inference: process.env.INFERENCE_API_KEY  // your LLM endpoint's key
  }
});

// Run the flow
const result = await engine.run({
  chat: [
    {
      role: 'user',
      content: "Hello, world!"
    }
  ]
});
```

## Flow File Formats

The Workbench engine supports two flow file formats:

### Workbench Flow Archive — `.zwf` (Recommended)

The `.zwf` format is a ZIP-based archive that supports hierarchical imports and modular flow design. (`.zwf` is the current extension; the legacy `.zv1` extension refers to the same archive format and is still accepted.)

```
myflow.zwf
├── orchestration.json          # Main flow definition
├── imports/                    # Optional imports folder
│   └── a1b2c3d4-e5f6-7890-abcd-ef1234567890/   # Import folder (importId only)
│       ├── orchestration.json  # Import's flow definition
│       ├── README.md           # Optional documentation
│       └── imports/            # Optional nested imports
│           └── b2c3d4e5-f6g7-8901-bcde-f12345678901/
│               └── orchestration.json
```

**Benefits:**
- **Modular Design**: Break complex flows into reusable components
- **Version Control**: Track different versions of imports with snapshots
- **Hierarchical Imports**: Support unlimited nesting depth
- **Developer Friendly**: Can be renamed to `.zip` and explored manually
- **Backward Compatible**: Legacy JSON flows still work

**Import Naming Convention:**
- **New Format**: `{importId}` (simplified)
- **Example**: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
- **Legacy Format**: `{displayName}.{snapshot}.{uniqueId}` (backward compatible)
- **Version Info**: Stored in import's orchestration.json metadata
- **Requested Range**: Stored in main orchestration.json imports object

### Legacy JSON Format

The legacy format is a single JSON file with an optional `imports` array:

```json
{
  "nodes": [...],
  "links": [...],
  "imports": [
    {
      "id": "import-123",
      "display_name": "My Import",
      "nodes": [...],
      "links": [...]
    }
  ]
}
```

### Import Resolution

The `.zwf` archive format supports two import declaration styles:

**1. Imports Object (Recommended):**
```json
{
  "metadata": {
    "name": "My Flow",
    "version": "1.0.0"
  },
  "nodes": [...],
  "links": [...],
  "imports": {
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890": "^1.2.3",
    "b2c3d4e5-f6g7-8901-bcde-f12345678901": "~1.0.0",
    "c3d4e5f6-g7h8-9012-cdef-123456789012": "2.1.0",
    "d4e5f6g7-h8i9-0123-defg-234567890123": "latest"
  }
}
```

**Version Range Syntax:**
- **Exact**: `"1.2.3"` - Use exactly this version
- **Caret**: `"^1.2.3"` - Compatible with 1.x.x (allows 1.3.0, 1.9.9, but not 2.0.0)
- **Tilde**: `"~1.2.3"` - Compatible with 1.2.x (allows 1.2.4, 1.2.9, but not 1.3.0)
- **Greater**: `">=1.2.3"` - Version 1.2.3 or higher
- **Latest**: `"latest"` - Use the highest available version
- **Stable**: `"stable"` - Use the latest stable version

**Import ID Format:**
- Auto-generated UUIDs (e.g., `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`)
- System maps to folder names like `uuid.1.2.3` (actual resolved version)
- Tracks both requested range and resolved version

**2. Legacy Imports Array (Backward Compatible):**
```json
{
  "nodes": [...],
  "links": [...],
  "imports": [
    {
      "id": "import-123",
      "display_name": "My Import",
      "nodes": [...],
      "links": [...]
    }
  ]
}
```

**Migration:** Legacy JSON files are automatically converted to the new format when loaded.

## Core Concepts

### Nodes & Links

Nodes are the building blocks of your flow, connected by links that define data flow.

#### Node Types

1. **Input Nodes**
   - `input-data`: Structured data entry point
   - `input-chat`: Chat message arrays
   - `input-prompt`: String prompts
   
   ```json
   {
     "id": "input1",
     "type": "input-data",
     "settings": {
       "key": "userInput",
       "default_value": "Hello"
     }
   }
   ```

2. **Output Nodes**
   - `output-data`: Return structured data
   - `output-chat`: Return chat messages
   ```json
   {
     "id": "output1",
     "type": "output-data",
     "settings": {
       "key": "result"
     }
   }
   ```

3. **Constant Nodes**
   - Provide fixed values
   - No input connections required
   - Process first in execution order

4. **Testing Nodes**
   - `throw-error`: Always throws a custom error message
   - `null-bomb`: Randomly returns null/undefined based on probability
   - `self-healing-error`: Fails initially but succeeds on retry
   - `random-error`: Randomly throws errors based on probability

### Flow Processing

The engine follows a specific order of operations:

1. **Initialization**
   - Use `Workbench.create()` to asynchronously load node definitions and custom types
   - Validate flow structure
   - Setup execution environment
   - Initialize ErrorManager

2. **Execution Order**
   ```
   Constant Nodes → Input Nodes → Processing Nodes → Output/Terminal Nodes
   ```

3. **Terminal Node Handling**
   When no output nodes exist, the engine returns:
   ```javascript
   {
     partial: true,
     message: "Flow completed without output nodes",
     terminal_nodes: [
       {
         node_id: "node1",
         type: "processor",
         outputs: { ... }
       }
     ]
   }
   ```

### Input/Output System

The engine supports various data types and structures:

```javascript
// Input format
const inputs = {
  data: {
    key1: "value1",
    key2: 42
  },
  chat: [
    { role: "user", content: "Hello" }
  ],
  prompt: "Generate a story about..."
};

// Output format
const outputs = {
  data: result,
  chat: responseMessages
};
```

## API Keys & Security

The engine supports secure API key management for nodes that require external service authentication.

### Configuration

```javascript
const engine = await Workbench.create(flow, {
  keys: {
    inference: "sk-...",  // key for the LLM endpoint (default: OpenRouter)
  }
});
```

### Pointing at your own LLM

Every OpenAI-compatible LLM node runs against a single inference endpoint.
By default that's OpenRouter, but you can point it at **your own**
OpenAI-compatible endpoint (vLLM, Ollama, TGI, a LiteLLM proxy, or any
gateway) — nothing leaves your infrastructure:

```javascript
const engine = await Workbench.create(flow, {
  keys: { inference: process.env.MY_LLM_KEY },
  inferenceBaseURL: "https://llm.my-internal-host/v1",
});
```

The model ids in the flow (e.g. `openai/gpt-4o`) must be ones your endpoint
serves — a LiteLLM `model_list` mapping is the usual way to line these up.
A custom `inferenceBaseURL` sends plain OpenAI-shaped requests (the
OpenRouter-only payload fields are dropped automatically).

> **Aliases:** `keys.openrouter` and `openrouterBaseURL` are still accepted
> as backward-compatible aliases for `keys.inference` and `inferenceBaseURL`.

### Node Key Requirements

Nodes specify their key requirements in their configuration. All LLMs are configured by default to use the inference endpoint (OpenRouter unless overridden), but this can be overridden.

```json
{
  "config": {
    "needs_key_from": ["openai"],
    "display_name": "GPT-4 Node",
    "description": "Processes text with GPT-4"
  }
}
```

The engine validates key availability before execution.

## Event Handlers

Monitor and extend flow execution with event handlers:

```javascript
const engine = await Workbench.create(flow, {
  onNodeStart: async ({ nodeId, nodeType, timestamp, inputs, settings }) => {
    console.log(`Node ${nodeId} starting execution`);
    // Example: Track metrics in your own system
    // await yourMetricsService.recordNodeStart(nodeId, timestamp);
  },
  
  onNodeComplete: async ({ nodeId, nodeType, timestamp, inputs, outputs, settings }) => {
    console.log(`Node ${nodeId} completed execution`);
    // Example: Calculate and track execution duration
    // const duration = timestamp - startTime;
    // await yourMetricsService.recordNodeComplete(nodeId, duration);
  },

  onNodeUpdate: async ({ nodeId, nodeType, timestamp, data }) => {
    console.log(`Node ${nodeId} sent update:`, data);
    // Example: Handle real-time updates from nodes
  },
  
  onError: async (errorEvent) => {
    console.log('Error occurred:', errorEvent);
    // Example: Send to your error tracking service
    // await yourErrorTracker.recordError(errorEvent);
  }
});
```

Common use cases:
- Performance monitoring
- Progress tracking
- Streaming LLM tokens via onNodeUpdate
- Debug logging
- Resource management
- External system integration
- Error tracking and alerting

## Error Handling

The engine includes a comprehensive ErrorManager for centralized error handling and detailed error reporting.

### Error Types

- **`node`**: Errors occurring during node execution
- **`flow`**: Errors related to flow structure or validation
- **`system`**: System-level errors
- **`validation`**: Input/output validation errors
- **`timeout`**: Execution timeout errors
- **`resource`**: Resource allocation or access errors

### Error Context

When verbose mode is enabled, errors include rich execution context:

```javascript
{
  errorType: "node",
  message: "Node execution failed: Custom error message",
  executionId: "uuid-1234",
  nodeId: "node-1",
  nodeType: "custom-node",
  errorDetails: {
    timeline: [...],
    nodeCount: 5,
    nodesExecuted: 3,
    cost_summary: { total: 0.05, itemized: [...] }
  }
}
```

### Error Recovery

The engine supports both fatal and recoverable errors:

```javascript
// Fatal errors stop execution
if (errorType === 'system') {
  throw new Error('Critical system failure');
}

// Recoverable errors allow retry logic
if (errorType === 'node' && retryCount < maxRetries) {
  // Retry node execution
}
```

## Resource Management

### Cleanup

When using knowledge databases or complex flows with imports, it's important to clean up resources:

```javascript
const engine = await Workbench.create('./myflow.zwf', config);

try {
  const result = await engine.run(inputs);
  console.log(result);
} finally {
  // Always clean up to free memory and remove temporary files
  await engine.cleanup();
}
```

**What cleanup does:**
- Closes all SQLite database connections
- Removes temporary knowledge database files
- Clears internal caches and timelines
- Recursively cleans up imported engines

**When to call cleanup:**
- After completing a flow execution
- Before creating a new engine instance
- In error handling blocks
- When the application is shutting down

## Advanced Features

### Plugin System

Support for LLM plugins and tools:

```javascript
// Tool schema definition
{
  "name": "calculator",
  "description": "Performs calculations",
  "parameters": {
    "type": "object",
    "properties": {
      "operation": { "type": "string" },
      "numbers": { "type": "array" }
    }
  }
}
```

### MCP (Model Context Protocol) Support

Integrate with external tools via MCP:

```javascript
const engine = await Workbench.create(flow, {
  mcp: {
    tools: [
      {
        name: "getTime",
        description: "Get current time",
        url: "http://localhost:3000/mcp"
      }
    ]
  }
});
```

### Agent Memory

An agent can keep notes between conversations in a small folder of markdown:
`MEMORY.md` (a short index), `memory/<topic>.md`, and `people/<id>.md`. A flow
uses it through six nodes:

- **Memory** reads the memory at the start of a turn. Wire its `variables`
  output into a System Prompt's Variables and put `{{MEMORY}}` where the
  memory belongs. Its `guidance` setting is the text that tells the agent
  how to work its memory.
- **List / Read / Write / Edit / Delete Memory** are tools: attach the ones
  you want to the model. An agent with only List and Read can't change
  what it remembers.

Which memory a run uses is up to you:

```javascript
import Workbench, { MemoryStoreInterface } from "@zerowidth/workbench-sdk";

// A folder per end user
await Workbench.create(flow, { memory: { path: `./memory/${userId}` } });

// Or your own store: rows in a table, objects in a bucket
class RowsMemory extends MemoryStoreInterface {
  constructor(db, userId) { super(); this.db = db; this.userId = userId; }
  async list() { /* → [{ path, size }] */ }
  async read(path) { /* → string | null */ }
  async write(path, content) { /* … */ return { status: "applied" }; }
  async delete(path) { /* … */ return { status: "applied" }; }
}
await Workbench.create(flow, { memory: { instance: new RowsMemory(db, userId) } });
```

With neither, the engine keeps memory in-process and it's gone when the
process exits. Paths are checked and file sizes capped before your store is
called.

Three ways to key a memory:

- **One shared memory:** one store for everyone.
- **A memory per person:** a store per person, by whatever id you key it on.
- **Shared, with a page per person:** one shared store plus
  `memory: { instance, people: true, person: { id, name } }`. The Memory node
  reads in `people/<id>.md` for whoever is talking, and the agent can only see
  and change that one page, so one person's notes never reach another
  conversation. With no `person`, it sees no pages at all. The id becomes a
  file name, so it must be letters, digits, `.`, `_` and `-`: hash or slug
  an email first.

Optional store members: `held: true` with `write`/`delete` returning
`{ status: "held" }` when changes wait for a person to approve them, and
`pending()` for how many are waiting. An imported
sub-agent never sees its caller's memory: pass
`memory.forImport(importId) => ({ instance | path })` to give it its own.

### Running Code

Attach the **Run Code** tool to a model and it can write and run Python or
JavaScript: load a CSV, compute something exactly, draw a chart. The engine
never runs the code itself. You tell it where:

```javascript
// A sandbox service that speaks the HTTP contract below
await Workbench.create(flow, {
  codeExecutor: { url: "https://sandbox.example.com", apiKey: process.env.SANDBOX_KEY },
});

// Or your own executor over any sandbox you like
import { CodeExecutorInterface } from "@zerowidth/workbench-sdk";
class MySandbox extends CodeExecutorInterface {
  async capabilities() { return { languages: ["python"], sessions: true, files: true }; }
  async openSession() { /* → session id */ }
  async run({ language, code, timeoutMs, session }) {
    /* → { stdout, stderr, result?, files?: [{ path, mimeType, data (base64) }], error? } */
  }
  async closeSession(id) { /* … */ }
}
await Workbench.create(flow, { codeExecutor: { instance: new MySandbox() } });
```

The HTTP contract is three JSON calls: `POST /sessions` → `{ id }`,
`POST /run` with `{ language, code, timeoutMs, session? }` → the result above,
and `DELETE /sessions/:id`. Answer `410` when a session is gone.

Each run gets one session, opened on the first call and closed by
`cleanup()`, so variables and files carry over between the model's calls
within a run. A failure in the code comes back to the model as output (the
traceback is in `stderr`) so it can fix it; a time limit, lost session or
unreachable sandbox comes back as a tool error. Images the code produces
(`image/png`, `jpeg`, `gif`, `webp`) reach the model as pictures; other files
are listed by path, type and size. Printed output is capped at 20,000
characters per stream.

Run the sandbox with no network access and pass it no secrets: the code is
written by a model.

### Custom Node Types

Create custom nodes by implementing:
1. Configuration file (`nodeType.config.json`)
2. Process function (`nodeType.process.js`)

### Cost Tracking

Monitor resource usage with built-in cost tracking:

```javascript
const result = await engine.run(inputs);
console.log('Total cost:', result.cost_summary.total);
console.log('Itemized costs:', result.cost_summary.itemized);
```

## Testing & Development

To prevent duplication and stay organized, shared internal dependencies for each SDK are not kept in each language specific directory. Use the `sync_sdks.py` script at the root of this directory to pull in the `/nodes`, `/types`, and `/tests` to each SDK for development. Packaged bundles are shipped with this step already completed and this is not necessary for basic use OR if this package was installed via npm/yarn. You will only need to run the sync script if you are accessing this by checking out this repo directly.

```bash
python sync_sdks.py
```

Run the comprehensive test suites:

```bash
# Test individual nodes using their <node>.tests.json configuration
npm run test-nodes

# Test complete flows stored within /tests/flows
npm run test-flows
```

### Advanced Node Testing Options

The node testing script supports several command-line options for efficient development and debugging:

```bash
# Test all nodes (default behavior)
node tests/test.all-nodes.js

# Test a specific node only
node tests/test.all-nodes.js --node absolute
node tests/test.all-nodes.js --node anthropic-claude-3-5-sonnet

# Resume testing from a specific node (useful after failures)
node tests/test.all-nodes.js --start-from array-map

# Show help and usage information
node tests/test.all-nodes.js --help

# Legacy support: positional argument for single node
node tests/test.all-nodes.js absolute
```

**Use Cases:**
- **Single Node Testing**: Quickly test a specific node during development with `--node`
- **Resume Testing**: Continue from where a test run failed using `--start-from`
- **Debugging**: Focus on problematic nodes without running the entire suite
- **Development**: Test only the nodes you're actively working on

**Error Handling:**
- Invalid node names display available options
- Conflicting options (e.g., `--node` and `--start-from`) are rejected
- Nodes are processed in alphabetical order for consistent `--start-from` behavior

### Test Flow Format

Create test flows in `tests/flows/` directory:

```json
{
  "flow": {
    "nodes": [...],
    "links": [...]
  },
  "inputs": { ... },
  "expected": { ... },
  "expectedSchema": { ... },
  "expectedError": {
    "type": "node",
    "message": "Expected error message",
    "nodeId": "node-1",
    "nodeType": "custom-node"
  }
}
```

### Testing Utilities

The engine includes specialized testing nodes:

- **`throw-error`**: Test error handling scenarios
- **`null-bomb`**: Test null/undefined handling
- **`self-healing-error`**: Test retry and recovery logic
- **`random-error`**: Test probabilistic error conditions

## API Reference

### Workbench Class

```javascript
class Workbench {
  
  /**
   * Create a new Workbench instance (recommended)
   * @param {string|Object|Buffer} flow - File path (.zwf, .zv1, or .json), flow definition object, or ZIP data (Buffer)
   * @param {Object} config - Configuration options and context for the engine
   * @returns {Promise<Workbench>} Fully initialized Workbench instance
   */
  static async create(flow, config)
  
  /**
   * Run the flow and return the final output
   * @param {Object} inputs - Data to inject into input nodes
   * @param {number} timeout - Maximum execution time in milliseconds (default: 60000)
   * @returns {Promise<Object>} The final output from output nodes
   */
  async run(inputs, timeout = 60000)
  
  /**
   * Clean up resources including knowledge databases and temporary files
   * Call this when the engine is no longer needed to free up memory
   * @returns {Promise<void>}
   */
  async cleanup()
  
}
```

#### Creating Instances

**Recommended: Use the static `create` method**

```javascript
// Load from .zwf file (recommended format)
const engine = await Workbench.create('./myflow.zwf', config);

// Load from legacy JSON file
const engine = await Workbench.create('./legacy.json', config);

// Load from flow object
const engine = await Workbench.create(flowObject, config);

// Load from ZIP data in memory (Buffer)
const zipBuffer = fs.readFileSync('./myflow.zwf');
const engine = await Workbench.create(zipBuffer, config);
```

**Important: Clean up resources when done**
```javascript
// Always call cleanup when the engine is no longer needed
await engine.cleanup();
```

The static `create` method:
- **Auto-detects format**: Supports `.zwf` files (and legacy `.zv1`), `.json` files, flow objects, and ZIP data (Buffer)
- **Handles imports**: Loads hierarchical imports automatically
- **Validates structure**: Ensures flow integrity before execution
- **Loads dependencies**: Node definitions, custom types, and integrations
- **Memory efficient**: Can load `.zwf` files directly from memory without writing to disk
- **Returns ready instance**: Fully initialized and ready to run


### Configuration Options

The `config` object supports the following properties:

```javascript
const config = {
  
  // Optional: API keys for external services
  keys: {
    openai: "sk-...",
    gemini: "...",
    // ... other service keys
  },
  
  // Optional: Node execution event handlers
  onNodeStart: async (event) => {
    // event: { nodeId, nodeType, timestamp, inputs, settings }
  },
  
  onNodeComplete: async (event) => {
    // event: { nodeId, nodeType, timestamp, inputs, outputs, settings }
  },

  onNodeUpdated: async (event) => {
    // event: { nodeId, nodeType, timestamp, data }
  },
  
  // Optional: Error event handler
  onError: async (errorEvent) => {
    // errorEvent: { errorType, message, executionId, nodeId?, nodeType?, errorDetails?, originalError? }
  },
  
  // Optional: Maximum number of plugin calls per LLM node to prevent runaway loops (default: 10)
  maxPluginCalls: 10,
  
  // Optional: Execution ID for tracking (auto-generated if not provided)
  executionId: "custom-execution-id",

  // Optional: Enable debug logging
  debug: true

};
```

### Execution Results

When you run a flow, the engine returns detailed execution information:

```javascript
const result = await engine.run(inputs);

// Example result structure:
{
  // Flow outputs (from output nodes)
  outputs: {
    data: "processed result",
    chat: [{ role: "assistant", content: "response" }]
  },
  
  // Execution timeline with detailed node information
  timeline: [
    {
      nodeId: "node-1",
      nodeType: "input-data", 
      inputs: { /* node inputs */ },
      outputs: { /* node outputs */ },
      settings: { /* node settings */ },
      startTime: "2024-01-01T10:00:00.000Z",
      endTime: "2024-01-01T10:00:00.100Z", 
      durationMs: 100,
      status: "success" // or "error"
      // errorMessage: "error details" (if status is "error")
    }
    // ... more timeline entries
  ],
  
  // Cost tracking information
  cost_summary: {
    total: 0.05,
    itemized: [
      {
        node_id: "llm-1",
        node_type: "openai-gpt-4",
        total: 0.05,
        itemized: { /* detailed cost breakdown */ }
      }
    ]
  },
  
  // Any missing input values for partial executions
  inputsMissingValues: [],
  
  // Completion message, which is also used to communicate partial runs 
  message: "Completed."
}
```

## Examples

### Basic Data Flow
```json
{
  "nodes": [
    {
      "id": "input1",
      "type": "input-data",
      "settings": { "key": "text" }
    },
    {
      "id": "process1",
      "type": "text-transform",
      "settings": { "operation": "uppercase" }
    },
    {
      "id": "output1",
      "type": "output-data"
    }
  ],
  "links": [
    {
      "from": { "node_id": "input1", "port_name": "value" },
      "to": { "node_id": "process1", "port_name": "input" }
    },
    {
      "from": { "node_id": "process1", "port_name": "output" },
      "to": { "node_id": "output1", "port_name": "value" }
    }
  ]
}
```

### Error Testing Flow
```json
{
  "flow": {
    "nodes": [
      {
        "id": "input1",
        "type": "input-data",
        "settings": { "key": "test-value" }
      },
      {
        "id": "error-test",
        "type": "self-healing-error",
        "settings": {}
      }
    ],
    "links": [
      {
        "from": { "node_id": "input1", "port_name": "value" },
        "to": { "node_id": "error-test", "port_name": "value" }
      }
    ]
  },
  "inputs": { "test-value": "Recovery Test" },
  "expectedError": {
    "type": "node",
    "message": "Self-healing error: failing 1 time(s) before success",
    "nodeId": "error-test",
    "nodeType": "self-healing-error"
  }
}
```

## License

Apache 2.0 © ZeroWidth

---

This engine is part of the Workbench platform. Visit our [documentation](https://zerowidth.ai/docs) for more information about the visual Workbench designer and other platform features.
