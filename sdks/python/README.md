# zv1

A Python implementation of ZeroWidth's zv1 framework for executing AI and automation workflows through a visual node-based interface. Design flows on zv1.ai, export as JSON, and execute with precision and control.

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
- [Testing & Development](#testing--development)
- [API Reference](#api-reference)
- [Examples](#examples)

## Overview

The zv1 Flow Engine enables you to:
- Execute complex AI and automation workflows
- Connect various node types (data processing, AI models, tools, testing utilities)
- Handle asynchronous operations with precision
- Monitor and debug flow execution with detailed timelines
- Integrate with external systems and APIs
- Test error handling and recovery scenarios
- Manage costs and resource usage

## Installation

```bash
pip install zv1
```

Or install from source:

```bash
git clone https://github.com/zerowidth/zv1.git
cd zv1/sdks/python
pip install -e .
```

## Quick Start

```python
import asyncio
from zv1 import Zv1

async def main():
    # Create engine instance by passing the location of your configured flow
    engine = await Zv1.create('./path/to/myflow.zv1', {
        'keys': {
            'openrouter': 'your-api-key'
        }
    })

    # Run the flow
    result = await engine.run({
        'chat': [
            {
                'role': 'user',
                'content': 'Hello, world!'
            }
        ]
    })

    print(result['outputs'])

    # Clean up resources
    await engine.cleanup()

asyncio.run(main())
```

## Flow File Formats

The zv1 engine supports two flow file formats:

### New .zv1 Format (Recommended)

The new `.zv1` format is a ZIP-based archive that supports hierarchical imports and modular flow design:

```
myflow.zv1
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

## Core Concepts

### Nodes & Links

Nodes are the building blocks of your flow, connected by links that define data flow.

#### Node Types

1. **Input Nodes**
   - `input-data`: Structured data entry point
   - `input-chat`: Chat message arrays
   - `input-prompt`: String prompts

2. **Output Nodes**
   - `output-data`: Return structured data
   - `output-chat`: Return chat messages

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
   - Use `Zv1.create()` to asynchronously load node definitions and custom types
   - Validate flow structure
   - Setup execution environment
   - Initialize ErrorManager

2. **Execution Order**
   ```
   Constant Nodes → Input Nodes → Processing Nodes → Output/Terminal Nodes
   ```

3. **Terminal Node Handling**
   When no output nodes exist, the engine returns:
   ```python
   {
       'partial': True,
       'message': 'Flow completed without output nodes',
       'terminal_nodes': [
           {
               'node_id': 'node1',
               'type': 'processor',
               'outputs': { ... }
           }
       ]
   }
   ```

### Input/Output System

The engine supports various data types and structures:

```python
# Input format
inputs = {
    'data': {
        'key1': 'value1',
        'key2': 42
    },
    'chat': [
        {'role': 'user', 'content': 'Hello'}
    ],
    'prompt': 'Generate a story about...'
}

# Output format
outputs = {
    'data': result,
    'chat': response_messages
}
```

## API Keys & Security

The engine supports secure API key management for nodes that require external service authentication.

### Configuration

```python
engine = await Zv1.create(flow, {
    'keys': {
        'openrouter': 'sk-...',  # OpenRouter API key
    }
})
```

### Node Key Requirements

Nodes specify their key requirements in their configuration. All LLMs are configured by default to use OpenRouter, but this can be overridden.

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

```python
async def on_node_start(event):
    print(f"Node {event['node_id']} starting execution")

async def on_node_complete(event):
    print(f"Node {event['node_id']} completed execution")

async def on_node_update(event):
    print(f"Node {event['node_id']} sent update:", event['data'])

async def on_error(error_event):
    print('Error occurred:', error_event)

engine = await Zv1.create(flow, {
    'on_node_start': on_node_start,
    'on_node_complete': on_node_complete,
    'on_node_update': on_node_update,
    'on_error': on_error
})
```

Common use cases:
- Performance monitoring
- Progress tracking
- Streaming LLM tokens via on_node_update
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

```python
{
    'error_type': 'node',
    'message': 'Node execution failed: Custom error message',
    'execution_id': 'uuid-1234',
    'node_id': 'node-1',
    'node_type': 'custom-node',
    'error_details': {
        'timeline': [...],
        'node_count': 5,
        'nodes_executed': 3,
        'cost_summary': {'total': 0.05, 'itemized': [...]}
    }
}
```

## Resource Management

### Cleanup

When using knowledge databases or complex flows with imports, it's important to clean up resources:

```python
engine = await Zv1.create('./myflow.zv1', config)

try:
    result = await engine.run(inputs)
    print(result)
finally:
    # Always clean up to free memory and remove temporary files
    await engine.cleanup()
```

**What cleanup does:**
- Closes all SQLite database connections
- Removes temporary knowledge database files
- Clears internal caches and timelines
- Recursively cleans up imported engines

## Advanced Features

### Plugin System

Support for LLM plugins and tools:

```python
# Tool schema definition
{
    'name': 'calculator',
    'description': 'Performs calculations',
    'parameters': {
        'type': 'object',
        'properties': {
            'operation': {'type': 'string'},
            'numbers': {'type': 'array'}
        }
    }
}
```

### MCP (Model Context Protocol) Support

Integrate with external tools via MCP:

```python
engine = await Zv1.create(flow, {
    'mcp': {
        'tools': [
            {
                'name': 'getTime',
                'description': 'Get current time',
                'url': 'http://localhost:3000/mcp'
            }
        ]
    }
})
```

### Custom Node Types

Create custom nodes by implementing:
1. Configuration file (`nodeType.config.json`)
2. Process function (`nodeType.process.py`)

### Cost Tracking

Monitor resource usage with built-in cost tracking:

```python
result = await engine.run(inputs)
print('Total cost:', result['cost_summary']['total'])
print('Itemized costs:', result['cost_summary']['itemized'])
```

## Testing & Development

To prevent duplication and stay organized, shared internal dependencies for each SDK are not kept in each language specific directory. Use the `sync_sdks.py` script at the root of this directory to pull in the `/nodes`, `/types`, and `/tests` to each SDK for development. Packaged bundles are shipped with this step already completed.

```bash
python sync_sdks.py
```

Run the comprehensive test suites:

```bash
# Test individual nodes using their <node>.tests.json configuration
python -m pytest tests/test_all_nodes.py

# Or run specific tests
python -m pytest tests/test_all_nodes.py -k "test_node_name"
```

## API Reference

### Zv1 Class

```python
class Zv1:

    @classmethod
    async def create(cls, flow, config: dict = None) -> 'Zv1':
        """
        Create a new Zv1 instance (recommended).

        Args:
            flow: File path (.zv1 or .json), flow definition dict, or bytes
            config: Configuration options and context for the engine

        Returns:
            Fully initialized Zv1 instance
        """

    async def run(self, inputs: dict, timeout: int = 60000) -> dict:
        """
        Run the flow and return the final output.

        Args:
            inputs: Data to inject into input nodes
            timeout: Maximum execution time in milliseconds (default: 60000)

        Returns:
            The final output from output nodes
        """

    async def cleanup(self) -> None:
        """
        Clean up resources including knowledge databases and temporary files.
        Call this when the engine is no longer needed to free up memory.
        """
```

### Configuration Options

```python
config = {
    # Optional: API keys for external services
    'keys': {
        'openai': 'sk-...',
        'gemini': '...',
        # ... other service keys
    },

    # Optional: Node execution event handlers
    'on_node_start': async_callback,      # (event) -> None
    'on_node_complete': async_callback,   # (event) -> None
    'on_node_update': async_callback,     # (event) -> None

    # Optional: Error event handler
    'on_error': async_callback,           # (error_event) -> None

    # Optional: Maximum number of plugin calls per LLM node (default: 10)
    'max_plugin_calls': 10,

    # Optional: Execution ID for tracking (auto-generated if not provided)
    'execution_id': 'custom-execution-id',

    # Optional: Enable debug logging
    'debug': True
}
```

### Execution Results

```python
result = await engine.run(inputs)

# Example result structure:
{
    # Flow outputs (from output nodes)
    'outputs': {
        'data': 'processed result',
        'chat': [{'role': 'assistant', 'content': 'response'}]
    },

    # Execution timeline with detailed node information
    'timeline': [
        {
            'node_id': 'node-1',
            'node_type': 'input-data',
            'inputs': {...},
            'outputs': {...},
            'settings': {...},
            'start_time': '2024-01-01T10:00:00.000Z',
            'end_time': '2024-01-01T10:00:00.100Z',
            'duration_ms': 100,
            'status': 'success'  # or 'error'
        }
        # ... more timeline entries
    ],

    # Cost tracking information
    'cost_summary': {
        'total': 0.05,
        'itemized': [...]
    },

    # Completion message
    'message': 'Completed.'
}
```

## Examples

### Basic Data Flow

```python
import asyncio
from zv1 import Zv1

async def main():
    flow = {
        'nodes': [
            {
                'id': 'input1',
                'type': 'input-data',
                'settings': {'key': 'text'}
            },
            {
                'id': 'process1',
                'type': 'text-transform',
                'settings': {'operation': 'uppercase'}
            },
            {
                'id': 'output1',
                'type': 'output-data'
            }
        ],
        'links': [
            {
                'from': {'node_id': 'input1', 'port_name': 'value'},
                'to': {'node_id': 'process1', 'port_name': 'input'}
            },
            {
                'from': {'node_id': 'process1', 'port_name': 'output'},
                'to': {'node_id': 'output1', 'port_name': 'value'}
            }
        ]
    }

    engine = await Zv1.create(flow)
    result = await engine.run({'text': 'hello world'})
    print(result['outputs'])  # {'data': 'HELLO WORLD'}

asyncio.run(main())
```

### Chat with LLM

```python
import asyncio
from zv1 import Zv1

async def main():
    engine = await Zv1.create('./chat-flow.zv1', {
        'keys': {
            'openrouter': 'your-api-key'
        }
    })

    result = await engine.run({
        'chat': [
            {'role': 'user', 'content': 'What is the capital of France?'}
        ]
    })

    print(result['outputs']['chat'])
    await engine.cleanup()

asyncio.run(main())
```

## License

Apache 2.0 © ZeroWidth

---

This engine is part of the zv1 platform. Visit our [documentation](https://zv1.ai/docs) for more information about the visual Workbench and other platform features.
