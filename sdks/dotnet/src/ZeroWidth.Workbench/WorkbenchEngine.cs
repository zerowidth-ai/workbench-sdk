using System.Text.Json;
using Microsoft.Extensions.Logging;
using ZeroWidth.Workbench.Cache;
using ZeroWidth.Workbench.Errors;
using ZeroWidth.Workbench.Loaders;
using ZeroWidth.Workbench.NodeProcessors;
using ZeroWidth.Workbench.Types;
using ZeroWidth.Workbench.Validators;

namespace ZeroWidth.Workbench;

/// <summary>
/// Timeline entry for tracking node execution.
/// </summary>
public record TimelineEntry
{
    /// <summary>Gets the node ID.</summary>
    public required string NodeId { get; init; }

    /// <summary>Gets the node type.</summary>
    public required string NodeType { get; init; }

    /// <summary>Gets the execution start timestamp.</summary>
    public long StartTimestamp { get; init; }

    /// <summary>Gets the execution end timestamp.</summary>
    public long? EndTimestamp { get; set; }

    /// <summary>Gets whether the node executed successfully.</summary>
    public bool Success { get; set; }

    /// <summary>Gets the error message if execution failed.</summary>
    public string? Error { get; set; }

    /// <summary>Gets the node inputs.</summary>
    public Dictionary<string, object?>? Inputs { get; init; }

    /// <summary>Gets the node outputs.</summary>
    public Dictionary<string, object?>? Outputs { get; set; }

    /// <summary>Gets execution metrics (tokens, cost, etc.).</summary>
    public Dictionary<string, object?>? Metrics { get; set; }

    /// <summary>Gets the execution duration in milliseconds.</summary>
    public long DurationMs => EndTimestamp.HasValue ? EndTimestamp.Value - StartTimestamp : 0;
}

/// <summary>
/// Result of flow execution.
/// </summary>
public record ExecutionResult
{
    /// <summary>Gets whether execution completed successfully.</summary>
    public bool Success { get; init; }

    /// <summary>Gets the execution outputs.</summary>
    public Dictionary<string, object?> Outputs { get; init; } = new();

    /// <summary>Gets the execution timeline.</summary>
    public List<TimelineEntry> Timeline { get; init; } = new();

    /// <summary>Gets any errors that occurred.</summary>
    public List<ErrorEvent> Errors { get; init; } = new();

    /// <summary>Gets the total execution time in milliseconds.</summary>
    public long TotalDurationMs { get; init; }

    /// <summary>Gets aggregated metrics.</summary>
    public Dictionary<string, object?> Metrics { get; init; } = new();
}

/// <summary>
/// Configuration options for the WorkbenchEngine engine.
/// </summary>
public class WorkbenchOptions
{
    /// <summary>Gets or sets the flow to execute.</summary>
    public object? Flow { get; set; }

    /// <summary>Gets or sets the API keys for integrations.</summary>
    public Dictionary<string, object?>? Keys { get; set; }

    /// <summary>Gets or sets the path to the nodes directory.</summary>
    public string? NodesDir { get; set; }

    /// <summary>Gets or sets the path to the types directory.</summary>
    public string? TypesDir { get; set; }

    /// <summary>Gets or sets the execution timeout in milliseconds.</summary>
    public int TimeoutMs { get; set; } = 300000; // 5 minutes

    /// <summary>Gets or sets the maximum concurrent nodes.</summary>
    public int MaxConcurrency { get; set; } = 10;

    /// <summary>Gets or sets whether to enable debug logging.</summary>
    public bool Debug { get; set; }

    /// <summary>Gets or sets the logger instance.</summary>
    public ILogger? Logger { get; set; }

    /// <summary>Gets or sets the node update callback.</summary>
    public Action<NodeUpdateEvent>? OnNodeUpdate { get; set; }

    /// <summary>Gets or sets additional integrations.</summary>
    public Dictionary<string, object>? Integrations { get; set; }
}

/// <summary>
/// Event raised when a node updates during execution.
/// </summary>
public record NodeUpdateEvent
{
    /// <summary>Gets the event count.</summary>
    public int Count { get; init; }

    /// <summary>Gets the node type.</summary>
    public string? NodeType { get; init; }

    /// <summary>Gets the node ID.</summary>
    public string? NodeId { get; init; }

    /// <summary>Gets the event timestamp.</summary>
    public long Timestamp { get; init; }

    /// <summary>Gets the event data.</summary>
    public Dictionary<string, object?>? Data { get; init; }
}

/// <summary>
/// The main zv1 engine for executing node-based AI flows.
/// </summary>
public class WorkbenchEngine : IAsyncDisposable
{
    private readonly WorkbenchOptions _options;
    private readonly ILogger? _logger;
    private readonly CacheManager _cache;
    private readonly ErrorManager _errorManager;
    private readonly List<TimelineEntry> _timeline;
    private readonly SemaphoreSlim _concurrencyLimiter;

    private Dictionary<string, NodeDefinition> _nodes = new();
    private Dictionary<string, TypeInfo> _customTypes = new();
    private Dictionary<string, object> _integrations = new();
    private Dictionary<string, object?>? _currentInputs;
    private JsonElement _flow;
    private bool _initialized;

    /// <summary>
    /// Gets the cache manager.
    /// </summary>
    public CacheManager Cache => _cache;

    /// <summary>
    /// Gets the error manager.
    /// </summary>
    public ErrorManager Errors => _errorManager;

    /// <summary>
    /// Gets the execution timeline.
    /// </summary>
    public IReadOnlyList<TimelineEntry> Timeline => _timeline.AsReadOnly();

    /// <summary>
    /// Gets whether the engine has been initialized.
    /// </summary>
    public bool IsInitialized => _initialized;

    /// <summary>
    /// Initializes a new instance of the WorkbenchEngine class.
    /// </summary>
    /// <param name="options">Engine configuration options.</param>
    public WorkbenchEngine(WorkbenchOptions? options = null)
    {
        _options = options ?? new WorkbenchOptions();
        _logger = _options.Logger;
        _cache = new CacheManager();
        _errorManager = new ErrorManager(_logger);
        _timeline = new List<TimelineEntry>();
        _concurrencyLimiter = new SemaphoreSlim(_options.MaxConcurrency);
    }

    /// <summary>
    /// Creates and initializes a new WorkbenchEngine engine instance.
    /// </summary>
    /// <param name="options">Engine configuration options.</param>
    /// <returns>An initialized WorkbenchEngine engine.</returns>
    public static async Task<WorkbenchEngine> CreateAsync(WorkbenchOptions options)
    {
        var engine = new WorkbenchEngine(options);
        await engine.InitializeAsync();
        return engine;
    }

    /// <summary>
    /// Initializes the engine by loading nodes, types, and integrations.
    /// </summary>
    public async Task InitializeAsync()
    {
        if (_initialized)
            return;

        // Initialize node processors
        NodeProcessorRegistry.Initialize();

        var nodesDir = _options.NodesDir ?? WorkbenchEngineLoaders.GetNodesDir();
        var typesDir = _options.TypesDir ?? WorkbenchEngineLoaders.GetTypesDir();

        // Load nodes
        _nodes = await WorkbenchEngineLoaders.LoadNodesAsync(nodesDir);
        _logger?.LogDebug("Loaded {Count} node definitions", _nodes.Count);

        // Load custom types
        _customTypes = await TypeSystem.LoadCustomTypesAsync(typesDir);
        _logger?.LogDebug("Loaded {Count} custom types", _customTypes.Count);

        // Load integrations
        if (_options.Integrations != null)
        {
            foreach (var (name, integration) in _options.Integrations)
            {
                _integrations[name] = integration;
            }
        }

        // Load flow if provided
        if (_options.Flow != null)
        {
            _flow = await WorkbenchEngineLoaders.DetectAndLoadFlowAsync(_options.Flow);
        }

        // Validate keys
        if (_options.Keys != null)
        {
            var nodeConfigs = _nodes.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value.Config);
            WorkbenchEngineValidators.ValidateKeys(nodeConfigs, _options.Keys);
        }

        _initialized = true;
    }

    /// <summary>
    /// Executes the loaded flow with the given inputs.
    /// </summary>
    /// <param name="inputs">Input values for input nodes.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The execution result.</returns>
    public async Task<ExecutionResult> RunAsync(
        Dictionary<string, object?>? inputs = null,
        CancellationToken cancellationToken = default)
    {
        if (!_initialized)
        {
            throw new InvalidOperationException("Engine not initialized. Call InitializeAsync() first.");
        }

        var startTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        _timeline.Clear();
        _cache.Clear();
        _errorManager.Clear();
        _currentInputs = inputs;

        try
        {
            // Validate flow
            var nodeConfigs = _nodes.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value.Config);
            var (inputNodes, entryNodes) = WorkbenchEngineValidators.ValidateFlow(_flow, nodeConfigs);

            // Initialize inputs in cache
            if (inputs != null)
            {
                foreach (var (key, value) in inputs)
                {
                    _cache.Set(key, value);
                }
            }

            // Get all flow nodes and links
            var flowNodes = _flow.GetProperty("nodes").EnumerateArray().ToList();
            var flowLinks = _flow.TryGetProperty("links", out var links)
                ? links.EnumerateArray().ToList()
                : new List<JsonElement>();

            // Execute with timeout
            using var timeoutCts = new CancellationTokenSource(_options.TimeoutMs);
            using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken, timeoutCts.Token);

            // Start execution from entry nodes
            var executionTasks = new List<Task>();

            foreach (var entryNode in entryNodes)
            {
                executionTasks.Add(ExecuteNodeAsync(entryNode, flowNodes, flowLinks, linkedCts.Token));
            }

            foreach (var inputNode in inputNodes)
            {
                executionTasks.Add(ExecuteNodeAsync(inputNode, flowNodes, flowLinks, linkedCts.Token));
            }

            await Task.WhenAll(executionTasks);

            var endTime = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

            // Collect outputs from output nodes
            var outputs = CollectOutputs(flowNodes);

            return new ExecutionResult
            {
                Success = !_errorManager.HasCriticalErrors,
                Outputs = outputs,
                Timeline = _timeline.ToList(),
                Errors = _errorManager.Errors.ToList(),
                TotalDurationMs = endTime - startTime,
                Metrics = CalculateMetrics()
            };
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (OperationCanceledException)
        {
            var error = new Errors.TimeoutException(
                $"Execution timed out after {_options.TimeoutMs}ms",
                _options.TimeoutMs);
            _errorManager.RecordError(error);

            return new ExecutionResult
            {
                Success = false,
                Errors = _errorManager.Errors.ToList(),
                Timeline = _timeline.ToList(),
                TotalDurationMs = _options.TimeoutMs
            };
        }
        catch (Exception ex)
        {
            _errorManager.RecordError(ex);

            return new ExecutionResult
            {
                Success = false,
                Errors = _errorManager.Errors.ToList(),
                Timeline = _timeline.ToList(),
                TotalDurationMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - startTime
            };
        }
    }

    private async Task ExecuteNodeAsync(
        JsonElement node,
        List<JsonElement> flowNodes,
        List<JsonElement> flowLinks,
        CancellationToken cancellationToken)
    {
        var nodeId = node.GetProperty("id").GetString()!;
        var nodeType = node.GetProperty("type").GetString()!;

        if (!_nodes.TryGetValue(nodeType, out var nodeDef))
        {
            _errorManager.RecordError(new NodeException(
                $"Unknown node type: {nodeType}",
                nodeId,
                nodeType));
            return;
        }

        await _concurrencyLimiter.WaitAsync(cancellationToken);

        var timelineEntry = new TimelineEntry
        {
            NodeId = nodeId,
            NodeType = nodeType,
            StartTimestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
        };

        try
        {
            // Collect inputs
            var inputs = CollectNodeInputs(node, flowLinks);
            timelineEntry = timelineEntry with { Inputs = inputs };

            // Get settings
            var settings = node.TryGetProperty("settings", out var s)
                ? JsonSerializer.Deserialize<Dictionary<string, object?>>(s.GetRawText()) ?? new()
                : new Dictionary<string, object?>();

            // Validate inputs
            WorkbenchEngineValidators.ValidateInputs(nodeDef.Config, inputs, _customTypes);

            // Execute node
            Dictionary<string, object?> outputs;

            // First try the NodeDefinition's ProcessFunc, then the registry
            var processFunc = nodeDef.ProcessFunc ?? NodeProcessorRegistry.GetProcessor(nodeType);

            if (processFunc != null)
            {
                var context = new NodeProcessContext
                {
                    Inputs = inputs,
                    Settings = settings,
                    Config = new Dictionary<string, object?>
                    {
                        ["integrations"] = _integrations,
                        ["keys"] = _options.Keys,
                        ["flow_inputs"] = _currentInputs
                    },
                    NodeConfig = nodeDef.Config
                };

                outputs = await processFunc(context);
            }
            else
            {
                // No process function - pass through inputs
                outputs = inputs;
            }

            // Validate outputs
            WorkbenchEngineValidators.ValidateOutputs(nodeDef.Config, outputs, _customTypes);

            // Store outputs in cache
            foreach (var (key, value) in outputs)
            {
                _cache.Set($"{nodeId}.{key}", value);
            }

            timelineEntry.Outputs = outputs;
            timelineEntry.Success = true;
            timelineEntry.EndTimestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

            lock (_timeline)
            {
                _timeline.Add(timelineEntry);
            }

            // Propagate to downstream nodes
            await PropagateAsync(nodeId, flowNodes, flowLinks, cancellationToken);
        }
        catch (Exception ex)
        {
            timelineEntry.Success = false;
            timelineEntry.Error = ex.Message;
            timelineEntry.EndTimestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

            lock (_timeline)
            {
                _timeline.Add(timelineEntry);
            }

            _errorManager.RecordError(ex, nodeId, nodeType);
        }
        finally
        {
            _concurrencyLimiter.Release();
        }
    }

    private Dictionary<string, object?> CollectNodeInputs(
        JsonElement node,
        List<JsonElement> flowLinks)
    {
        var nodeId = node.GetProperty("id").GetString()!;
        var inputs = new Dictionary<string, object?>();

        // Find all links pointing to this node
        var incomingLinks = flowLinks.Where(link =>
            link.GetProperty("to").GetProperty("node_id").GetString() == nodeId);

        foreach (var link in incomingLinks)
        {
            var fromNodeId = link.GetProperty("from").GetProperty("node_id").GetString()!;
            var fromPort = link.GetProperty("from").TryGetProperty("port", out var fp)
                ? fp.GetString() ?? "output"
                : "output";
            var toPort = link.GetProperty("to").TryGetProperty("port", out var tp)
                ? tp.GetString() ?? "input"
                : "input";

            var cacheKey = $"{fromNodeId}.{fromPort}";
            if (_cache.Has(cacheKey))
            {
                inputs[toPort] = _cache.Get(cacheKey);
            }
        }

        return inputs;
    }

    private async Task PropagateAsync(
        string nodeId,
        List<JsonElement> flowNodes,
        List<JsonElement> flowLinks,
        CancellationToken cancellationToken)
    {
        // Find downstream nodes
        var outgoingLinks = flowLinks.Where(link =>
            link.GetProperty("from").GetProperty("node_id").GetString() == nodeId);

        var downstreamNodeIds = outgoingLinks
            .Select(link => link.GetProperty("to").GetProperty("node_id").GetString()!)
            .Distinct();

        var tasks = new List<Task>();

        foreach (var downstreamId in downstreamNodeIds)
        {
            var downstreamNode = flowNodes.FirstOrDefault(n =>
                n.GetProperty("id").GetString() == downstreamId);

            if (downstreamNode.ValueKind != JsonValueKind.Undefined)
            {
                // Check if all required inputs are available
                if (AreInputsReady(downstreamNode, flowLinks))
                {
                    tasks.Add(ExecuteNodeAsync(downstreamNode, flowNodes, flowLinks, cancellationToken));
                }
            }
        }

        await Task.WhenAll(tasks);
    }

    private bool AreInputsReady(JsonElement node, List<JsonElement> flowLinks)
    {
        var nodeId = node.GetProperty("id").GetString()!;

        var incomingLinks = flowLinks.Where(link =>
            link.GetProperty("to").GetProperty("node_id").GetString() == nodeId);

        foreach (var link in incomingLinks)
        {
            var fromNodeId = link.GetProperty("from").GetProperty("node_id").GetString()!;
            var fromPort = link.GetProperty("from").TryGetProperty("port", out var fp)
                ? fp.GetString() ?? "output"
                : "output";

            var cacheKey = $"{fromNodeId}.{fromPort}";
            if (!_cache.Has(cacheKey))
            {
                return false;
            }
        }

        return true;
    }

    private Dictionary<string, object?> CollectOutputs(List<JsonElement> flowNodes)
    {
        var outputs = new Dictionary<string, object?>();

        var outputNodes = flowNodes.Where(node =>
        {
            var nodeType = node.GetProperty("type").GetString();
            return nodeType?.StartsWith("output-") == true;
        });

        foreach (var outputNode in outputNodes)
        {
            var nodeId = outputNode.GetProperty("id").GetString()!;
            var settings = outputNode.TryGetProperty("settings", out var s)
                ? s
                : default;

            var key = settings.TryGetProperty("key", out var k)
                ? k.GetString() ?? "output"
                : "output";

            // Look for output value in cache
            foreach (var cacheKey in _cache.Keys)
            {
                if (cacheKey.StartsWith($"{nodeId}."))
                {
                    var outputName = cacheKey.Substring(nodeId.Length + 1);
                    outputs[key] = _cache.Get(cacheKey);
                    break;
                }
            }
        }

        return outputs;
    }

    private Dictionary<string, object?> CalculateMetrics()
    {
        var metrics = new Dictionary<string, object?>
        {
            ["total_nodes_executed"] = _timeline.Count,
            ["successful_nodes"] = _timeline.Count(t => t.Success),
            ["failed_nodes"] = _timeline.Count(t => !t.Success),
            ["total_duration_ms"] = _timeline.Sum(t => t.DurationMs)
        };

        // Aggregate any token/cost metrics from timeline entries
        long totalTokens = 0;
        double totalCost = 0;

        foreach (var entry in _timeline)
        {
            if (entry.Metrics != null)
            {
                if (entry.Metrics.TryGetValue("total_tokens", out var tokens) && tokens is long t)
                {
                    totalTokens += t;
                }
                if (entry.Metrics.TryGetValue("cost_total", out var cost) && cost is double c)
                {
                    totalCost += c;
                }
            }
        }

        if (totalTokens > 0) metrics["total_tokens"] = totalTokens;
        if (totalCost > 0) metrics["total_cost"] = totalCost;

        return metrics;
    }

    /// <summary>
    /// Disposes of the engine resources.
    /// </summary>
    public async ValueTask DisposeAsync()
    {
        _concurrencyLimiter.Dispose();

        // Dispose any integrations that implement IAsyncDisposable
        foreach (var integration in _integrations.Values)
        {
            if (integration is IAsyncDisposable asyncDisposable)
            {
                await asyncDisposable.DisposeAsync();
            }
            else if (integration is IDisposable disposable)
            {
                disposable.Dispose();
            }
        }

        GC.SuppressFinalize(this);
    }
}
