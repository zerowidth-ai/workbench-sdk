using System.Text.Json;
using ZeroWidth.Workbench.Errors;
using ZeroWidth.Workbench.Types;

namespace ZeroWidth.Workbench.Validators;

/// <summary>
/// Validation utilities for the zv1 engine.
/// </summary>
public static class WorkbenchEngineValidators
{
    /// <summary>
    /// Checks if a key value is an OAuth key structure.
    /// </summary>
    /// <param name="keyValue">The key value to check.</param>
    /// <returns>True if the key is an OAuth key structure.</returns>
    public static bool IsOAuthKey(object? keyValue)
    {
        if (keyValue is not JsonElement element || element.ValueKind != JsonValueKind.Object)
        {
            if (keyValue is not IDictionary<string, object?> dict)
                return false;

            return dict.ContainsKey("access_token") && dict.ContainsKey("on_refresh");
        }

        return element.TryGetProperty("access_token", out _) &&
               element.TryGetProperty("on_refresh", out _);
    }

    /// <summary>
    /// Validates keys for all nodes that specify needs_key_from.
    /// </summary>
    /// <param name="nodes">Dictionary mapping node types to their definitions.</param>
    /// <param name="keys">Dictionary of API keys.</param>
    /// <exception cref="ValidationException">If required keys are missing.</exception>
    public static void ValidateKeys(
        Dictionary<string, JsonElement> nodes,
        Dictionary<string, object?> keys)
    {
        foreach (var (nodeType, nodeDef) in nodes)
        {
            if (!nodeDef.TryGetProperty("config", out var config))
                continue;

            if (!config.TryGetProperty("needs_key_from", out var needsKeyFrom))
                continue;

            var requiredKeys = needsKeyFrom.ValueKind switch
            {
                JsonValueKind.String => new[] { needsKeyFrom.GetString()! },
                JsonValueKind.Array => needsKeyFrom.EnumerateArray()
                    .Select(k => k.GetString()!)
                    .ToArray(),
                _ => Array.Empty<string>()
            };

            var missingKeys = requiredKeys
                .Where(key => !keys.ContainsKey(key))
                .ToList();

            if (missingKeys.Count > 0)
            {
                throw new ValidationException(
                    $"Node type '{nodeType}' requires the following missing keys: {string.Join(", ", missingKeys)}",
                    field: "keys");
            }
        }
    }

    /// <summary>
    /// Validates flow structure and returns input/entry nodes.
    /// </summary>
    /// <param name="flow">The flow definition.</param>
    /// <param name="nodes">Dictionary mapping node types to their definitions.</param>
    /// <returns>Tuple of (inputNodes, entryNodes).</returns>
    /// <exception cref="FlowException">If flow structure is invalid.</exception>
    public static (List<JsonElement> InputNodes, List<JsonElement> EntryNodes) ValidateFlow(
        JsonElement flow,
        Dictionary<string, JsonElement> nodes)
    {
        var flowNodes = flow.TryGetProperty("nodes", out var nodesEl)
            ? nodesEl.EnumerateArray().ToList()
            : new List<JsonElement>();

        var flowLinks = flow.TryGetProperty("links", out var linksEl)
            ? linksEl.EnumerateArray().ToList()
            : new List<JsonElement>();

        // Get all node IDs
        var nodeIds = flowNodes
            .Where(n => n.TryGetProperty("id", out _))
            .Select(n => n.GetProperty("id").GetString()!)
            .ToHashSet();

        // Validate all links reference existing nodes
        var invalidLinks = flowLinks.Where(link =>
        {
            var fromId = link.GetProperty("from").GetProperty("node_id").GetString();
            var toId = link.GetProperty("to").GetProperty("node_id").GetString();
            return !nodeIds.Contains(fromId!) || !nodeIds.Contains(toId!);
        }).ToList();

        if (invalidLinks.Count > 0)
        {
            var desc = string.Join(", ", invalidLinks.Select(link =>
            {
                var fromId = link.GetProperty("from").GetProperty("node_id").GetString();
                var toId = link.GetProperty("to").GetProperty("node_id").GetString();
                return $"{fromId} -> {toId}";
            }));

            throw new FlowException(
                $"Flow contains {invalidLinks.Count} invalid link(s) referencing non-existent nodes: {desc}");
        }

        // Find input nodes
        var inputNodes = flowNodes.Where(node =>
        {
            if (!node.TryGetProperty("type", out var typeEl))
                return false;

            var nodeType = typeEl.GetString();
            if (nodeType == null || !nodes.TryGetValue(nodeType, out var nodeDef))
                return false;

            if (!nodeDef.TryGetProperty("config", out var config))
                return false;

            return config.TryGetProperty("is_input", out var isInput) && isInput.GetBoolean();
        }).ToList();

        // Find entry nodes (constant nodes without inputs, not linked as plugins)
        var entryNodes = flowNodes.Where(node =>
        {
            if (!node.TryGetProperty("type", out var typeEl) ||
                !node.TryGetProperty("id", out var idEl))
                return false;

            var nodeType = typeEl.GetString();
            var nodeId = idEl.GetString();

            if (nodeType == null || !nodes.TryGetValue(nodeType, out var nodeDef))
                return false;

            if (!nodeDef.TryGetProperty("config", out var config))
                return false;

            // Must be a constant node
            if (!config.TryGetProperty("is_constant", out var isConstant) || !isConstant.GetBoolean())
                return false;

            // Must not have any input connections
            var hasInputs = flowLinks.Any(link =>
                link.GetProperty("to").GetProperty("node_id").GetString() == nodeId);
            if (hasInputs)
                return false;

            // Exclude if it's a plugin linked as a plugin
            var isPlugin = config.TryGetProperty("is_plugin", out var isPluginEl) && isPluginEl.GetBoolean();
            var isLinkedAsPlugin = flowLinks.Any(link =>
            {
                var fromId = link.GetProperty("from").GetProperty("node_id").GetString();
                var linkType = link.TryGetProperty("type", out var t) ? t.GetString() : null;
                return fromId == nodeId && linkType == "plugin";
            });

            if (isPlugin && isLinkedAsPlugin)
                return false;

            return true;
        }).ToList();

        // Ensure there's at least one entry point
        if (inputNodes.Count == 0 && entryNodes.Count == 0)
        {
            throw new FlowException(
                "Flow must have at least one input node or constant node without inputs to start execution");
        }

        return (inputNodes, entryNodes);
    }

    /// <summary>
    /// Validates inputs against the node's configuration.
    /// </summary>
    /// <param name="nodeConfig">The node's configuration.</param>
    /// <param name="inputs">The inputs dictionary to validate.</param>
    /// <param name="customTypes">Optional custom type definitions.</param>
    /// <exception cref="ValidationException">If inputs are invalid.</exception>
    public static void ValidateInputs(
        JsonElement nodeConfig,
        Dictionary<string, object?> inputs,
        Dictionary<string, TypeInfo>? customTypes = null)
    {
        var displayName = nodeConfig.TryGetProperty("display_name", out var dn)
            ? dn.GetString() ?? "Node"
            : "Node";

        if (!nodeConfig.TryGetProperty("inputs", out var inputDefs))
            return;

        foreach (var inputDef in inputDefs.EnumerateArray())
        {
            var name = inputDef.GetProperty("name").GetString()!;
            var inputType = inputDef.TryGetProperty("type", out var t) ? t.GetString() ?? "any" : "any";
            var required = inputDef.TryGetProperty("required", out var r) && r.GetBoolean();

            var hasValue = inputs.TryGetValue(name, out var value);

            // Check if required and missing
            if (required && (!hasValue || value == null))
            {
                throw new ValidationException(
                    $"{displayName} is missing required input: {name}",
                    field: name);
            }

            // Check if type matches
            if (hasValue && value != null && !TypeSystem.TypeCheck(value, inputType, customTypes))
            {
                throw new ValidationException(
                    $"{displayName} has a type mismatch for input '{name}': Expected {inputType}, got {value.GetType().Name}",
                    field: name);
            }
        }
    }

    /// <summary>
    /// Validates outputs against the node's configuration.
    /// Logs warnings for mismatches but doesn't throw.
    /// </summary>
    /// <param name="nodeConfig">The node's configuration.</param>
    /// <param name="outputs">The outputs dictionary to validate.</param>
    /// <param name="customTypes">Optional custom type definitions.</param>
    public static void ValidateOutputs(
        JsonElement nodeConfig,
        Dictionary<string, object?> outputs,
        Dictionary<string, TypeInfo>? customTypes = null)
    {
        var displayName = nodeConfig.TryGetProperty("display_name", out var dn)
            ? dn.GetString() ?? "Node"
            : "Node";

        if (!nodeConfig.TryGetProperty("outputs", out var outputDefs))
            return;

        foreach (var outputDef in outputDefs.EnumerateArray())
        {
            var name = outputDef.GetProperty("name").GetString()!;
            var outputType = outputDef.TryGetProperty("type", out var t) ? t.GetString() ?? "any" : "any";

            if (outputs.TryGetValue(name, out var value) &&
                value != null &&
                !TypeSystem.TypeCheck(value, outputType, customTypes))
            {
                Console.Error.WriteLine(
                    $"Warning: {displayName} output '{name}' type mismatch: Expected {outputType}, got {value.GetType().Name}");
            }
        }
    }
}
