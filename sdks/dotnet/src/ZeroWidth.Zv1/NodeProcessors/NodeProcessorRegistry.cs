namespace ZeroWidth.Zv1.NodeProcessors;

using ZeroWidth.Zv1.Loaders;

/// <summary>
/// Registry for node process functions.
/// Maps node types to their corresponding process functions.
/// </summary>
public static class NodeProcessorRegistry
{
    private static readonly Dictionary<string, Func<NodeProcessContext, Task<Dictionary<string, object?>>>> _processors = new();
    private static bool _initialized;

    /// <summary>
    /// Initializes the registry with built-in node processors.
    /// </summary>
    public static void Initialize()
    {
        if (_initialized)
            return;

        // Register basic nodes
        BasicNodes.Register();

        _initialized = true;
    }

    /// <summary>
    /// Registers a node processor.
    /// </summary>
    /// <param name="nodeType">The node type identifier.</param>
    /// <param name="processor">The process function.</param>
    public static void Register(
        string nodeType,
        Func<NodeProcessContext, Task<Dictionary<string, object?>>> processor)
    {
        _processors[nodeType] = processor;
    }

    /// <summary>
    /// Gets the processor for a node type, if registered.
    /// </summary>
    /// <param name="nodeType">The node type identifier.</param>
    /// <returns>The process function, or null if not registered.</returns>
    public static Func<NodeProcessContext, Task<Dictionary<string, object?>>>? GetProcessor(string nodeType)
    {
        return _processors.TryGetValue(nodeType, out var processor) ? processor : null;
    }

    /// <summary>
    /// Checks if a processor is registered for a node type.
    /// </summary>
    /// <param name="nodeType">The node type identifier.</param>
    /// <returns>True if a processor is registered.</returns>
    public static bool HasProcessor(string nodeType) => _processors.ContainsKey(nodeType);

    /// <summary>
    /// Gets the list of registered node types.
    /// </summary>
    public static IEnumerable<string> RegisteredTypes => _processors.Keys;

    /// <summary>
    /// Clears all registered processors (useful for testing).
    /// </summary>
    public static void Clear()
    {
        _processors.Clear();
        _initialized = false;
    }
}
