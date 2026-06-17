using System.IO.Compression;
using System.Text.Json;

namespace ZeroWidth.Workbench.Loaders;

/// <summary>
/// Node definition with config and optional process function.
/// </summary>
public class NodeDefinition
{
    /// <summary>Gets the node configuration.</summary>
    public required JsonElement Config { get; init; }

    /// <summary>Gets the process function delegate, if available.</summary>
    public Func<NodeProcessContext, Task<Dictionary<string, object?>>>? ProcessFunc { get; init; }

    /// <summary>Gets the path to the process file.</summary>
    public string? ProcessPath { get; init; }
}

/// <summary>
/// Context passed to node process functions.
/// </summary>
public record NodeProcessContext
{
    /// <summary>Gets the node inputs.</summary>
    public required Dictionary<string, object?> Inputs { get; init; }

    /// <summary>Gets the node settings.</summary>
    public required Dictionary<string, object?> Settings { get; init; }

    /// <summary>Gets the engine configuration.</summary>
    public required Dictionary<string, object?> Config { get; init; }

    /// <summary>Gets the node configuration.</summary>
    public required JsonElement NodeConfig { get; init; }
}

/// <summary>
/// Loaders for nodes, flows, and integrations.
/// </summary>
public static class WorkbenchEngineLoaders
{
    /// <summary>
    /// Loads all node definitions from the nodes directory.
    /// </summary>
    /// <param name="nodesDir">Path to the nodes directory.</param>
    /// <returns>Dictionary mapping node type to node definition.</returns>
    public static async Task<Dictionary<string, NodeDefinition>> LoadNodesAsync(string nodesDir)
    {
        var nodes = new Dictionary<string, NodeDefinition>();

        if (!Directory.Exists(nodesDir))
        {
            return nodes;
        }

        foreach (var nodeDir in Directory.GetDirectories(nodesDir))
        {
            var nodeName = Path.GetFileName(nodeDir);
            var configPath = Path.Combine(nodeDir, $"{nodeName}.config.json");
            var processPath = Path.Combine(nodeDir, $"{nodeName}.process.cs");

            if (!File.Exists(configPath))
                continue;

            try
            {
                var configJson = await File.ReadAllTextAsync(configPath);
                var config = JsonDocument.Parse(configJson).RootElement;

                nodes[nodeName] = new NodeDefinition
                {
                    Config = config,
                    ProcessPath = File.Exists(processPath) ? processPath : null
                };
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Failed to load node {nodeName}: {ex.Message}");
            }
        }

        return nodes;
    }

    /// <summary>
    /// Detects and loads a flow from various sources.
    /// </summary>
    /// <param name="source">The flow source (path, JSON string, or bytes).</param>
    /// <returns>The parsed flow as JsonElement.</returns>
    public static async Task<JsonElement> DetectAndLoadFlowAsync(object source)
    {
        // If it's already a JsonElement, return it
        if (source is JsonElement element)
            return element;

        // If it's a string path or JSON
        if (source is string str)
        {
            // Check if it's a file path
            if (File.Exists(str))
            {
                if (str.EndsWith(".zv1", StringComparison.OrdinalIgnoreCase))
                {
                    return await LoadWorkbenchEngineFileAsync(str);
                }
                else
                {
                    var json = await File.ReadAllTextAsync(str);
                    return JsonDocument.Parse(json).RootElement;
                }
            }

            // Try to parse as JSON
            return JsonDocument.Parse(str).RootElement;
        }

        // If it's bytes (zv1 file content)
        if (source is byte[] bytes)
        {
            return await LoadWorkbenchEngineFromBytesAsync(bytes);
        }

        if (source is Stream stream)
        {
            return await LoadWorkbenchEngineFromStreamAsync(stream);
        }

        throw new ArgumentException("Invalid flow source. Expected file path, JSON string, bytes, or stream.");
    }

    /// <summary>
    /// Loads a .zv1 file (ZIP format containing flow.json).
    /// </summary>
    /// <param name="path">Path to the .zv1 file.</param>
    /// <returns>The parsed flow.</returns>
    public static async Task<JsonElement> LoadWorkbenchEngineFileAsync(string path)
    {
        var bytes = await File.ReadAllBytesAsync(path);
        return await LoadWorkbenchEngineFromBytesAsync(bytes);
    }

    /// <summary>
    /// Loads a .zv1 file from bytes.
    /// </summary>
    /// <param name="bytes">The .zv1 file content.</param>
    /// <returns>The parsed flow.</returns>
    public static async Task<JsonElement> LoadWorkbenchEngineFromBytesAsync(byte[] bytes)
    {
        using var stream = new MemoryStream(bytes);
        return await LoadWorkbenchEngineFromStreamAsync(stream);
    }

    /// <summary>
    /// Loads a .zv1 file from a stream.
    /// </summary>
    /// <param name="stream">The stream containing .zv1 content.</param>
    /// <returns>The parsed flow.</returns>
    public static async Task<JsonElement> LoadWorkbenchEngineFromStreamAsync(Stream stream)
    {
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);

        var flowEntry = archive.GetEntry("flow.json")
            ?? throw new FileNotFoundException("flow.json not found in .zv1 archive");

        using var entryStream = flowEntry.Open();
        using var reader = new StreamReader(entryStream);
        var json = await reader.ReadToEndAsync();

        var flow = JsonDocument.Parse(json).RootElement;

        // Process imports if present
        if (flow.TryGetProperty("imports", out var imports) && imports.ValueKind == JsonValueKind.Array)
        {
            var importsList = new List<JsonElement>();

            foreach (var import in imports.EnumerateArray())
            {
                if (import.TryGetProperty("importId", out var importId))
                {
                    // Look for embedded import in the archive
                    var importPath = $"imports/{importId.GetString()}.json";
                    var importEntry = archive.GetEntry(importPath);

                    if (importEntry != null)
                    {
                        using var importStream = importEntry.Open();
                        using var importReader = new StreamReader(importStream);
                        var importJson = await importReader.ReadToEndAsync();
                        var importData = JsonDocument.Parse(importJson).RootElement;

                        // Merge import data with import definition
                        var mergedImport = MergeImport(import, importData);
                        importsList.Add(mergedImport);
                    }
                    else
                    {
                        importsList.Add(import);
                    }
                }
                else
                {
                    importsList.Add(import);
                }
            }

            // Reconstruct flow with processed imports
            return ReconstructFlowWithImports(flow, importsList);
        }

        return flow;
    }

    private static JsonElement MergeImport(JsonElement importDef, JsonElement importData)
    {
        var merged = new Dictionary<string, JsonElement>();

        // Copy import definition properties
        foreach (var prop in importDef.EnumerateObject())
        {
            merged[prop.Name] = prop.Value;
        }

        // Overlay import data properties
        foreach (var prop in importData.EnumerateObject())
        {
            merged[prop.Name] = prop.Value;
        }

        var json = JsonSerializer.Serialize(merged);
        return JsonDocument.Parse(json).RootElement;
    }

    private static JsonElement ReconstructFlowWithImports(JsonElement flow, List<JsonElement> imports)
    {
        var flowDict = new Dictionary<string, object?>();

        foreach (var prop in flow.EnumerateObject())
        {
            if (prop.Name == "imports")
            {
                flowDict["imports"] = imports;
            }
            else
            {
                flowDict[prop.Name] = prop.Value;
            }
        }

        var json = JsonSerializer.Serialize(flowDict);
        return JsonDocument.Parse(json).RootElement;
    }

    /// <summary>
    /// Converts legacy import format to current format.
    /// </summary>
    /// <param name="imports">The imports array.</param>
    /// <returns>Converted imports.</returns>
    public static List<JsonElement> ConvertLegacyImports(JsonElement imports)
    {
        var result = new List<JsonElement>();

        foreach (var import in imports.EnumerateArray())
        {
            // Check for legacy format markers
            if (import.TryGetProperty("flow", out _))
            {
                // Legacy format - flatten the structure
                var converted = new Dictionary<string, object?>();

                foreach (var prop in import.EnumerateObject())
                {
                    if (prop.Name == "flow")
                    {
                        foreach (var flowProp in prop.Value.EnumerateObject())
                        {
                            converted[flowProp.Name] = flowProp.Value;
                        }
                    }
                    else
                    {
                        converted[prop.Name] = prop.Value;
                    }
                }

                var json = JsonSerializer.Serialize(converted);
                result.Add(JsonDocument.Parse(json).RootElement);
            }
            else
            {
                result.Add(import);
            }
        }

        return result;
    }

    /// <summary>
    /// Gets the SDK root directory.
    /// </summary>
    public static string GetSdkDir()
    {
        var assembly = typeof(WorkbenchEngineLoaders).Assembly;
        var assemblyDir = Path.GetDirectoryName(assembly.Location)!;

        // Navigate up to find the SDK root
        var current = new DirectoryInfo(assemblyDir);
        while (current != null)
        {
            if (Directory.Exists(Path.Combine(current.FullName, "nodes")))
            {
                return current.FullName;
            }
            current = current.Parent;
        }

        return assemblyDir;
    }

    /// <summary>
    /// Gets the nodes directory path.
    /// </summary>
    public static string GetNodesDir() => Path.Combine(GetSdkDir(), "nodes");

    /// <summary>
    /// Gets the types directory path.
    /// </summary>
    public static string GetTypesDir() => Path.Combine(GetSdkDir(), "types");
}
