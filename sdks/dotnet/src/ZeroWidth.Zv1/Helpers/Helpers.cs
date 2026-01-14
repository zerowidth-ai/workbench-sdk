using System.Text.Json;
using System.Text.RegularExpressions;

namespace ZeroWidth.Zv1.Helpers;

/// <summary>
/// Utility helper functions for the zv1 engine.
/// </summary>
public static partial class Zv1Helpers
{
    /// <summary>
    /// Creates a safe tool name by replacing invalid characters with underscores.
    /// </summary>
    /// <param name="name">The original name.</param>
    /// <returns>A safe name containing only alphanumeric characters and underscores.</returns>
    public static string CreateSafeToolName(string name)
    {
        if (string.IsNullOrEmpty(name))
            return "tool";

        // Replace any non-alphanumeric characters (except underscores) with underscores
        var safe = SafeNameRegex().Replace(name, "_");

        // Ensure it doesn't start with a number
        if (char.IsDigit(safe[0]))
        {
            safe = "_" + safe;
        }

        return safe;
    }

    [GeneratedRegex(@"[^a-zA-Z0-9_]")]
    private static partial Regex SafeNameRegex();

    /// <summary>
    /// Checks if a node is a remote MCP tool node.
    /// </summary>
    /// <param name="nodeConfig">The node configuration.</param>
    /// <returns>True if the node is a remote MCP tool.</returns>
    public static bool IsRemoteMcpTool(JsonElement nodeConfig)
    {
        return nodeConfig.TryGetProperty("is_mcp_tool", out var isMcp) && isMcp.GetBoolean() &&
               nodeConfig.TryGetProperty("is_remote", out var isRemote) && isRemote.GetBoolean();
    }

    /// <summary>
    /// Checks if a node is a manual tool node.
    /// </summary>
    /// <param name="nodeConfig">The node configuration.</param>
    /// <returns>True if the node is a manual tool.</returns>
    public static bool IsManualToolNode(JsonElement nodeConfig)
    {
        return nodeConfig.TryGetProperty("category", out var category) &&
               category.GetString() == "manual-tool";
    }

    /// <summary>
    /// Maps a type string to JSON Schema type.
    /// </summary>
    /// <param name="typeString">The type string (e.g., "string", "number").</param>
    /// <returns>JSON Schema type object.</returns>
    public static Dictionary<string, object> MapTypeToJsonSchema(string typeString)
    {
        var type = typeString.ToLowerInvariant().Trim();

        return type switch
        {
            "string" => new Dictionary<string, object> { ["type"] = "string" },
            "number" => new Dictionary<string, object> { ["type"] = "number" },
            "integer" => new Dictionary<string, object> { ["type"] = "integer" },
            "boolean" => new Dictionary<string, object> { ["type"] = "boolean" },
            "array" => new Dictionary<string, object> { ["type"] = "array" },
            "object" => new Dictionary<string, object> { ["type"] = "object" },
            "any" => new Dictionary<string, object>(), // Empty schema accepts anything
            _ => new Dictionary<string, object> { ["type"] = "string" } // Default to string
        };
    }

    /// <summary>
    /// Extracts text content from a message content field.
    /// Handles both string content and array of content items.
    /// </summary>
    /// <param name="content">The content to extract text from.</param>
    /// <returns>The extracted text content.</returns>
    public static string ExtractTextFromContent(object? content)
    {
        if (content == null)
            return string.Empty;

        if (content is string str)
            return str;

        if (content is JsonElement element)
        {
            if (element.ValueKind == JsonValueKind.String)
                return element.GetString() ?? string.Empty;

            if (element.ValueKind == JsonValueKind.Array)
            {
                var textParts = new List<string>();
                foreach (var item in element.EnumerateArray())
                {
                    if (item.TryGetProperty("type", out var type) &&
                        type.GetString() == "text" &&
                        item.TryGetProperty("text", out var text))
                    {
                        textParts.Add(text.GetString() ?? string.Empty);
                    }
                }
                return string.Join("", textParts);
            }
        }

        if (content is IEnumerable<object> list)
        {
            var textParts = new List<string>();
            foreach (var item in list)
            {
                if (item is IDictionary<string, object> dict &&
                    dict.TryGetValue("type", out var type) &&
                    type?.ToString() == "text" &&
                    dict.TryGetValue("text", out var text))
                {
                    textParts.Add(text?.ToString() ?? string.Empty);
                }
            }
            return string.Join("", textParts);
        }

        return content.ToString() ?? string.Empty;
    }

    /// <summary>
    /// Deep merges two dictionaries, with source values overriding target values.
    /// </summary>
    /// <param name="target">The target dictionary.</param>
    /// <param name="source">The source dictionary to merge from.</param>
    /// <returns>A new merged dictionary.</returns>
    public static Dictionary<string, object?> DeepMerge(
        IDictionary<string, object?>? target,
        IDictionary<string, object?>? source)
    {
        var result = new Dictionary<string, object?>();

        if (target != null)
        {
            foreach (var kvp in target)
            {
                result[kvp.Key] = kvp.Value;
            }
        }

        if (source != null)
        {
            foreach (var kvp in source)
            {
                if (kvp.Value is IDictionary<string, object?> sourceDict &&
                    result.TryGetValue(kvp.Key, out var existing) &&
                    existing is IDictionary<string, object?> existingDict)
                {
                    result[kvp.Key] = DeepMerge(existingDict, sourceDict);
                }
                else
                {
                    result[kvp.Key] = kvp.Value;
                }
            }
        }

        return result;
    }

    /// <summary>
    /// Ensures a value is a list.
    /// </summary>
    /// <typeparam name="T">The element type.</typeparam>
    /// <param name="value">The value to convert.</param>
    /// <returns>A list containing the value(s).</returns>
    public static List<T> EnsureList<T>(object? value)
    {
        if (value == null)
            return new List<T>();

        if (value is List<T> list)
            return list;

        if (value is IEnumerable<T> enumerable)
            return enumerable.ToList();

        if (value is T single)
            return new List<T> { single };

        return new List<T>();
    }

    /// <summary>
    /// Safely gets a nested property value from a dictionary.
    /// </summary>
    /// <param name="dict">The dictionary to search.</param>
    /// <param name="path">The dot-separated path (e.g., "settings.temperature").</param>
    /// <returns>The value at the path, or null if not found.</returns>
    public static object? SafeGet(IDictionary<string, object?>? dict, string path)
    {
        if (dict == null || string.IsNullOrEmpty(path))
            return null;

        var parts = path.Split('.');
        object? current = dict;

        foreach (var part in parts)
        {
            if (current is IDictionary<string, object?> currentDict)
            {
                if (currentDict.TryGetValue(part, out var value))
                {
                    current = value;
                }
                else
                {
                    return null;
                }
            }
            else if (current is JsonElement element)
            {
                if (element.TryGetProperty(part, out var prop))
                {
                    current = prop;
                }
                else
                {
                    return null;
                }
            }
            else
            {
                return null;
            }
        }

        return current;
    }

    /// <summary>
    /// Normalizes messages to ensure consistent format.
    /// </summary>
    /// <param name="messages">The messages to normalize.</param>
    /// <returns>Normalized messages list.</returns>
    public static List<Dictionary<string, object?>> NormalizeMessages(
        IEnumerable<Dictionary<string, object?>>? messages)
    {
        if (messages == null)
            return new List<Dictionary<string, object?>>();

        return messages.Select(msg =>
        {
            var normalized = new Dictionary<string, object?>(msg);

            // Ensure role exists
            if (!normalized.ContainsKey("role"))
            {
                normalized["role"] = "user";
            }

            // Ensure content exists
            if (!normalized.ContainsKey("content"))
            {
                normalized["content"] = "";
            }

            return normalized;
        }).ToList();
    }
}
