# zv1

A .NET implementation of ZeroWidth's zv1 framework for executing AI and automation workflows through a visual node-based interface. Design flows on zv1.ai, export as JSON, and execute with precision and control.

[![Apache 2.0 License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![NuGet](https://img.shields.io/nuget/v/ZeroWidth.Zv1.svg)](https://www.nuget.org/packages/ZeroWidth.Zv1)

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

### NuGet Package

```bash
dotnet add package ZeroWidth.Zv1
```

Or via Package Manager Console:

```powershell
Install-Package ZeroWidth.Zv1
```

### From Source

```bash
git clone https://github.com/zerowidth/zv1.git
cd zv1/sdks/dotnet
dotnet build
```

## Quick Start

```csharp
using ZeroWidth.Zv1;

// Create engine instance by passing the location of your configured flow
await using var engine = await Zv1Engine.CreateAsync("./path/to/myflow.zv1", new Zv1Config
{
    Keys = new Dictionary<string, object?>
    {
        ["openrouter"] = "your-api-key"
    }
});

// Run the flow
var result = await engine.RunAsync(new Dictionary<string, object?>
{
    ["chat"] = new List<object>
    {
        new Dictionary<string, object?>
        {
            ["role"] = "user",
            ["content"] = "Hello, world!"
        }
    }
});

Console.WriteLine(result.Outputs);
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
   - Use `Zv1Engine.CreateAsync()` to asynchronously load node definitions and custom types
   - Validate flow structure
   - Setup execution environment
   - Initialize ErrorManager

2. **Execution Order**
   ```
   Constant Nodes → Input Nodes → Processing Nodes → Output/Terminal Nodes
   ```

3. **Terminal Node Handling**
   When no output nodes exist, the engine returns:
   ```csharp
   new ExecutionResult
   {
       Partial = true,
       Message = "Flow completed without output nodes",
       TerminalNodes = new List<TerminalNode>
       {
           new TerminalNode
           {
               NodeId = "node1",
               Type = "processor",
               Outputs = { ... }
           }
       }
   }
   ```

### Input/Output System

The engine supports various data types and structures:

```csharp
// Input format
var inputs = new Dictionary<string, object?>
{
    ["data"] = new Dictionary<string, object?>
    {
        ["key1"] = "value1",
        ["key2"] = 42
    },
    ["chat"] = new List<object>
    {
        new Dictionary<string, object?> { ["role"] = "user", ["content"] = "Hello" }
    },
    ["prompt"] = "Generate a story about..."
};

// Output format
var outputs = result.Outputs;
// outputs["data"], outputs["chat"], etc.
```

## API Keys & Security

The engine supports secure API key management for nodes that require external service authentication.

### Configuration

```csharp
var engine = await Zv1Engine.CreateAsync(flow, new Zv1Config
{
    Keys = new Dictionary<string, object?>
    {
        ["openrouter"] = "sk-..."  // OpenRouter API key
    }
});
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

```csharp
var engine = await Zv1Engine.CreateAsync(flow, new Zv1Config
{
    OnNodeStart = async (node) =>
    {
        Console.WriteLine($"Node {node.NodeId} starting execution");
    },

    OnNodeComplete = async (node) =>
    {
        Console.WriteLine($"Node {node.NodeId} completed execution");
    },

    OnNodeUpdate = async (update) =>
    {
        Console.WriteLine($"Node {update.NodeId} sent update: {update.Data}");
    },

    OnError = async (error) =>
    {
        Console.WriteLine($"Error occurred: {error.Message}");
    }
});
```

Common use cases:
- Performance monitoring
- Progress tracking
- Streaming LLM tokens via OnNodeUpdate
- Debug logging
- Resource management
- External system integration
- Error tracking and alerting

## Error Handling

The engine includes a comprehensive ErrorManager for centralized error handling and detailed error reporting.

### Error Types

- **`NodeError`**: Errors occurring during node execution
- **`FlowError`**: Errors related to flow structure or validation
- **`SystemError`**: System-level errors
- **`ValidationError`**: Input/output validation errors
- **`TimeoutError`**: Execution timeout errors
- **`ResourceError`**: Resource allocation or access errors

### Exception Hierarchy

```csharp
try
{
    var result = await engine.RunAsync(inputs);
}
catch (NodeException ex)
{
    Console.WriteLine($"Node {ex.NodeId} failed: {ex.Message}");
}
catch (FlowException ex)
{
    Console.WriteLine($"Flow error: {ex.Message}");
}
catch (ValidationException ex)
{
    Console.WriteLine($"Validation error for {ex.Field}: {ex.Message}");
}
catch (Zv1Exception ex)
{
    Console.WriteLine($"Engine error: {ex.Message}");
}
```

## Resource Management

### Cleanup with IAsyncDisposable

The engine implements `IAsyncDisposable` for automatic cleanup:

```csharp
await using var engine = await Zv1Engine.CreateAsync("./myflow.zv1", config);

var result = await engine.RunAsync(inputs);
Console.WriteLine(result);
// Resources are automatically cleaned up when leaving the using block
```

Or manually:

```csharp
var engine = await Zv1Engine.CreateAsync("./myflow.zv1", config);

try
{
    var result = await engine.RunAsync(inputs);
    Console.WriteLine(result);
}
finally
{
    await engine.DisposeAsync();
}
```

**What cleanup does:**
- Closes all SQLite database connections
- Removes temporary knowledge database files
- Clears internal caches and timelines
- Recursively cleans up imported engines

## Advanced Features

### Plugin System

Support for LLM plugins and tools:

```csharp
// Tool schema definition
var tool = new ToolDefinition
{
    Name = "calculator",
    Description = "Performs calculations",
    Parameters = new Dictionary<string, object>
    {
        ["type"] = "object",
        ["properties"] = new Dictionary<string, object>
        {
            ["operation"] = new Dictionary<string, object> { ["type"] = "string" },
            ["numbers"] = new Dictionary<string, object> { ["type"] = "array" }
        }
    }
};
```

### MCP (Model Context Protocol) Support

Integrate with external tools via MCP:

```csharp
var engine = await Zv1Engine.CreateAsync(flow, new Zv1Config
{
    Mcp = new McpConfig
    {
        Tools = new List<McpTool>
        {
            new McpTool
            {
                Name = "getTime",
                Description = "Get current time",
                Url = "http://localhost:3000/mcp"
            }
        }
    }
});
```

### Custom Node Types

Create custom nodes by implementing:
1. Configuration file (`nodeType.config.json`)
2. Process function (`nodeType.process.cs`)

### Cost Tracking

Monitor resource usage with built-in cost tracking:

```csharp
var result = await engine.RunAsync(inputs);
Console.WriteLine($"Total cost: {result.CostSummary?.Total}");

foreach (var item in result.CostSummary?.Itemized ?? Enumerable.Empty<CostItem>())
{
    Console.WriteLine($"  {item.NodeId}: {item.Total}");
}
```

## Testing & Development

To prevent duplication and stay organized, shared internal dependencies for each SDK are not kept in each language specific directory. Use the `sync_sdks.py` script at the root of this directory to pull in the `/nodes`, `/types`, and `/tests` to each SDK for development. Packaged bundles are shipped with this step already completed.

```bash
python sync_sdks.py
```

Build and run tests:

```bash
cd sdks/dotnet
dotnet restore
dotnet build
dotnet test
```

### Test Runner

The SDK includes a test runner for node tests:

```csharp
using ZeroWidth.Zv1.Testing;

var runner = new NodeTestRunner("./nodes");
var summary = await runner.RunAllTestsAsync();

NodeTestRunner.PrintResults(summary);
```

Run specific node tests:

```csharp
// Test a specific node
var summary = await runner.RunNodeTestsAsync("add");

// Test starting from a specific node
var summary = await runner.RunTestsStartingFromAsync("array-map");
```

## API Reference

### Zv1Engine Class

```csharp
public class Zv1Engine : IAsyncDisposable
{
    /// <summary>
    /// Create a new Zv1Engine instance (recommended).
    /// </summary>
    /// <param name="flow">File path (.zv1 or .json), flow definition, or stream</param>
    /// <param name="config">Configuration options and context for the engine</param>
    /// <returns>Fully initialized Zv1Engine instance</returns>
    public static Task<Zv1Engine> CreateAsync(object flow, Zv1Config? config = null);

    /// <summary>
    /// Run the flow and return the final output.
    /// </summary>
    /// <param name="inputs">Data to inject into input nodes</param>
    /// <param name="timeout">Maximum execution time (default: 60 seconds)</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>The execution result with outputs and metadata</returns>
    public Task<ExecutionResult> RunAsync(
        Dictionary<string, object?>? inputs = null,
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Clean up resources including knowledge databases and temporary files.
    /// </summary>
    public ValueTask DisposeAsync();
}
```

### Configuration Options

```csharp
public class Zv1Config
{
    // Optional: API keys for external services
    public Dictionary<string, object?>? Keys { get; set; }

    // Optional: Node execution event handlers
    public Func<NodeEvent, Task>? OnNodeStart { get; set; }
    public Func<NodeEvent, Task>? OnNodeComplete { get; set; }
    public Func<NodeUpdateEvent, Task>? OnNodeUpdate { get; set; }

    // Optional: Error event handler
    public Func<ErrorEvent, Task>? OnError { get; set; }

    // Optional: Maximum number of plugin calls per LLM node (default: 10)
    public int MaxPluginCalls { get; set; } = 10;

    // Optional: Execution ID for tracking (auto-generated if not provided)
    public string? ExecutionId { get; set; }

    // Optional: Enable debug logging
    public bool Debug { get; set; }
}
```

### Execution Results

```csharp
var result = await engine.RunAsync(inputs);

// ExecutionResult structure:
public record ExecutionResult
{
    // Flow outputs (from output nodes)
    public Dictionary<string, object?>? Outputs { get; init; }

    // Execution timeline with detailed node information
    public List<TimelineEntry>? Timeline { get; init; }

    // Cost tracking information
    public CostSummary? CostSummary { get; init; }

    // Whether the execution was partial (no output nodes)
    public bool Partial { get; init; }

    // Completion message
    public string? Message { get; init; }
}

public record TimelineEntry
{
    public string NodeId { get; init; }
    public string NodeType { get; init; }
    public Dictionary<string, object?>? Inputs { get; init; }
    public Dictionary<string, object?>? Outputs { get; init; }
    public DateTimeOffset StartTime { get; init; }
    public DateTimeOffset EndTime { get; init; }
    public long DurationMs { get; init; }
    public string Status { get; init; }  // "success" or "error"
    public string? ErrorMessage { get; init; }
}
```

## Examples

### Basic Data Flow

```csharp
using ZeroWidth.Zv1;

var flow = new Dictionary<string, object?>
{
    ["nodes"] = new List<object>
    {
        new Dictionary<string, object?>
        {
            ["id"] = "input1",
            ["type"] = "input-data",
            ["settings"] = new Dictionary<string, object?> { ["key"] = "text" }
        },
        new Dictionary<string, object?>
        {
            ["id"] = "process1",
            ["type"] = "text-transform",
            ["settings"] = new Dictionary<string, object?> { ["operation"] = "uppercase" }
        },
        new Dictionary<string, object?>
        {
            ["id"] = "output1",
            ["type"] = "output-data"
        }
    },
    ["links"] = new List<object>
    {
        new Dictionary<string, object?>
        {
            ["from"] = new Dictionary<string, object?> { ["node_id"] = "input1", ["port_name"] = "value" },
            ["to"] = new Dictionary<string, object?> { ["node_id"] = "process1", ["port_name"] = "input" }
        },
        new Dictionary<string, object?>
        {
            ["from"] = new Dictionary<string, object?> { ["node_id"] = "process1", ["port_name"] = "output" },
            ["to"] = new Dictionary<string, object?> { ["node_id"] = "output1", ["port_name"] = "value" }
        }
    }
};

await using var engine = await Zv1Engine.CreateAsync(flow);
var result = await engine.RunAsync(new Dictionary<string, object?> { ["text"] = "hello world" });
Console.WriteLine(result.Outputs?["data"]);  // "HELLO WORLD"
```

### Chat with LLM

```csharp
using ZeroWidth.Zv1;

await using var engine = await Zv1Engine.CreateAsync("./chat-flow.zv1", new Zv1Config
{
    Keys = new Dictionary<string, object?>
    {
        ["openrouter"] = Environment.GetEnvironmentVariable("OPENROUTER_API_KEY")
    }
});

var result = await engine.RunAsync(new Dictionary<string, object?>
{
    ["chat"] = new List<object>
    {
        new Dictionary<string, object?>
        {
            ["role"] = "user",
            ["content"] = "What is the capital of France?"
        }
    }
});

var chat = result.Outputs?["chat"] as List<object>;
Console.WriteLine(chat);
```

### Streaming with Event Handlers

```csharp
await using var engine = await Zv1Engine.CreateAsync("./streaming-flow.zv1", new Zv1Config
{
    Keys = new Dictionary<string, object?> { ["openrouter"] = apiKey },
    OnNodeUpdate = async (update) =>
    {
        if (update.Data?.TryGetValue("content", out var content) == true)
        {
            Console.Write(content);  // Stream tokens as they arrive
        }
    }
});

var result = await engine.RunAsync(inputs);
Console.WriteLine();  // Final newline after streaming
```

## License

Apache 2.0 © ZeroWidth

---

This engine is part of the zv1 platform. Visit our [documentation](https://zv1.ai/docs) for more information about the visual Workbench and other platform features.
