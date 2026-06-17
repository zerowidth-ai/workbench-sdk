# .NET SDK Development Status

**Last Updated**: January 2025
**Status**: Early Development (Not Yet Tested)

## Overview

The .NET SDK has been scaffolded with the core architecture in place, mirroring the patterns established in the Node.js and Python SDKs. However, it has not been compiled or tested yet.

## What's Been Implemented

### Core Engine (`src/ZeroWidth.Workbench/`)

| File | Status | Description |
|------|--------|-------------|
| `WorkbenchEngine.cs` | Complete | Main engine class with `CreateAsync()` and `RunAsync()` |
| `Cache/CacheManager.cs` | Complete | In-memory cache for node outputs |
| `Errors/ErrorManager.cs` | Complete | Centralized error handling |
| `Errors/WorkbenchEngineException.cs` | Complete | Custom exception types |
| `Loaders/Loaders.cs` | Complete | Flow and node config loading (.json and .zv1) |
| `Validators/Validators.cs` | Complete | Input/output validation |
| `Types/TypeSystem.cs` | Complete | Custom type definitions |
| `Helpers/Helpers.cs` | Complete | Utility functions |

### Node Processor System (`src/ZeroWidth.Workbench/NodeProcessors/`)

| File | Status | Description |
|------|--------|-------------|
| `NodeProcessorRegistry.cs` | **New** | Registry mapping node types to C# process functions |
| `BasicNodes.cs` | **New** | Implementations for `add`, `input-data`, `output-data` |

### Testing (`src/ZeroWidth.Workbench/Testing/`)

| File | Status | Description |
|------|--------|-------------|
| `NodeTestRunner.cs` | Complete | Unit test runner for individual nodes |
| `FlowTestRunner.cs` | **New** | Integration test runner for flow tests |

### Test Project (`tests/ZeroWidth.Workbench.Tests/`)

| File | Status | Description |
|------|--------|-------------|
| `FlowTests.cs` | **New** | xUnit test cases for flow tests |
| `CacheManagerTests.cs` | Existing | Unit tests for cache |
| `HelpersTests.cs` | Existing | Unit tests for helpers |
| `TypeSystemTests.cs` | Existing | Unit tests for type system |

### Integrations (`src/ZeroWidth.Workbench/Integrations/`)

| File | Status | Description |
|------|--------|-------------|
| `OpenRouterIntegration.cs` | Scaffolded | OpenRouter API client (needs testing) |
| `OpenAIIntegration.cs` | Scaffolded | OpenAI API client (needs testing) |
| `FirecrawlIntegration.cs` | Scaffolded | Firecrawl integration |
| `GoogleCustomSearchIntegration.cs` | Scaffolded | Google search integration |
| `HubSpotIntegration.cs` | Scaffolded | HubSpot integration |
| `NewsDataIntegration.cs` | Scaffolded | NewsData.io integration |
| `SqliteIntegration.cs` | Scaffolded | SQLite for knowledge bases |
| `OAuthManager.cs` | Scaffolded | OAuth token management |

## Architecture Decisions

### Node Processor Pattern

Similar to Python, we use a registry pattern instead of dynamic script loading:

```csharp
// Registration (in BasicNodes.cs)
NodeProcessorRegistry.Register("add", AddProcessor);

// Usage (in WorkbenchEngine.cs)
var processFunc = NodeProcessorRegistry.GetProcessor(nodeType);
var outputs = await processFunc(context);
```

### Process Function Signature

```csharp
// C# node processor signature
Task<Dictionary<string, object?>> ProcessFunc(NodeProcessContext context)

// Context contains:
public record NodeProcessContext
{
    public Dictionary<string, object?> Inputs { get; init; }
    public Dictionary<string, object?> Settings { get; init; }
    public Dictionary<string, object?> Config { get; init; }  // includes flow_inputs, integrations, keys
    public JsonElement NodeConfig { get; init; }
}
```

### Flow Input Handling

Input-data nodes access runtime inputs via `context.Config["flow_inputs"]`:

```csharp
// In InputDataProcessor
if (context.Config.TryGetValue("flow_inputs", out var flowInputsObj) &&
    flowInputsObj is Dictionary<string, object?> flowInputs &&
    flowInputs.TryGetValue(key, out var flowInputValue))
{
    value = flowInputValue;
}
```

## How to Set Up (Once .NET is Installed)

### Prerequisites

```bash
# Install .NET SDK (macOS)
brew install dotnet

# Verify installation
dotnet --version  # Should be 8.0+
```

### Build and Test

```bash
cd sdks/dotnet

# Restore dependencies
dotnet restore

# Build
dotnet build

# Run tests
dotnet test

# Run specific test
dotnet test --filter "AdditionTest_Legacy_ShouldPass"
```

### Expected Test Output

If everything works correctly:
```
[INFO] Running all flow tests (X files)
[INFO] Testing flow: flow.addition.json with inputs: {"a":3,"b":2}
  [RESULT] {"outputs":{"data":5}}
  [PASS] flow.addition.json
[INFO] Testing flow: flow.addition.zv1 with inputs: {"a":2,"b":3}
  [RESULT] {"outputs":{"data":5}}
  [PASS] flow.addition.zv1
...
```

## What Still Needs to Be Done

### Immediate (To Get Tests Passing)

1. **Build and fix any compilation errors** - The code hasn't been compiled yet
2. **Debug flow execution** - May need adjustments to link traversal logic
3. **Fix JSON deserialization** - Settings parsing may need tweaking

### Short Term (Basic Functionality)

1. **Add more basic node processors**:
   - `subtract`, `multiply`, `divide`
   - `string` (constant)
   - `number` (constant)

2. **Test .zv1 file loading** - ZIP extraction logic needs verification

3. **Validate cache key format** - Ensure `{nodeId}.{portName}` pattern works

### Medium Term (LLM Support)

1. **Test OpenRouter integration** - API calls, streaming, tool calls
2. **Add LLM node processors** - Claude, GPT-4, etc.
3. **Implement plugin/tool system** - For LLM function calling

### Long Term (Production Ready)

1. **Add remaining node processors** - Match Node.js/Python coverage
2. **Performance optimization** - Async patterns, connection pooling
3. **NuGet package publishing** - Distribution setup
4. **Documentation** - API docs, examples

## File Locations Reference

```
sdks/dotnet/
├── ZeroWidth.Workbench.sln              # Solution file
├── src/ZeroWidth.Workbench/
│   ├── ZeroWidth.Workbench.csproj       # Main project
│   ├── WorkbenchEngine.cs                     # Engine entry point
│   ├── NodeProcessors/
│   │   ├── NodeProcessorRegistry.cs
│   │   └── BasicNodes.cs          # add, input-data, output-data
│   └── Testing/
│       ├── NodeTestRunner.cs
│       └── FlowTestRunner.cs
├── tests/
│   ├── flows/                     # Synced test flows
│   │   ├── flow.addition.json
│   │   ├── flow.addition.zv1
│   │   └── flow.addition.test.json
│   └── ZeroWidth.Workbench.Tests/
│       ├── ZeroWidth.Workbench.Tests.csproj
│       └── FlowTests.cs           # xUnit test cases
└── nodes/                         # Synced node configs
```

## Notes for Future Development

- The C# code follows similar patterns to Python but uses `async Task` instead of `async def`
- `Dictionary<string, object?>` is the C# equivalent of Python's `dict[str, Any]`
- `JsonElement` from System.Text.Json is used for parsing (not Newtonsoft.Json)
- The project targets .NET 8.0 (LTS release)
