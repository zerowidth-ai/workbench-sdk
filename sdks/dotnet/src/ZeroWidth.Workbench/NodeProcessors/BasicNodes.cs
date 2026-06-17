using System.Text.Json;
using ZeroWidth.Workbench.Loaders;

namespace ZeroWidth.Workbench.NodeProcessors;

/// <summary>
/// Basic node processors for fundamental operations.
/// </summary>
public static class BasicNodes
{
    /// <summary>
    /// Registers all basic node processors.
    /// </summary>
    public static void Register()
    {
        NodeProcessorRegistry.Register("add", AddProcessor);
        NodeProcessorRegistry.Register("input-data", InputDataProcessor);
        NodeProcessorRegistry.Register("output-data", OutputDataProcessor);
    }

    /// <summary>
    /// Add node - adds two numbers together.
    /// </summary>
    private static Task<Dictionary<string, object?>> AddProcessor(NodeProcessContext context)
    {
        var a = ToDouble(context.Inputs.GetValueOrDefault("a"));
        var b = ToDouble(context.Inputs.GetValueOrDefault("b"));

        return Task.FromResult(new Dictionary<string, object?>
        {
            ["result"] = a + b
        });
    }

    /// <summary>
    /// Input Data node - provides variable input from the user.
    /// </summary>
    private static Task<Dictionary<string, object?>> InputDataProcessor(NodeProcessContext context)
    {
        // Get the key from settings
        var key = GetStringSetting(context.Settings, "key") ?? "value";

        // Priority order for value:
        // 1. Flow inputs (runtime inputs passed to engine.run())
        // 2. Explicit value in settings
        // 3. default_value in settings
        object? value = null;

        // Check flow inputs first
        if (context.Config.TryGetValue("flow_inputs", out var flowInputsObj) &&
            flowInputsObj is Dictionary<string, object?> flowInputs &&
            flowInputs.TryGetValue(key, out var flowInputValue))
        {
            value = flowInputValue;
        }
        else if (context.Settings.TryGetValue("value", out var settingsValue) && settingsValue != null)
        {
            value = settingsValue;
        }
        else if (context.Settings.TryGetValue("default_value", out var defaultValue))
        {
            value = defaultValue;
        }

        // Type conversion based on settings
        var valueType = GetStringSetting(context.Settings, "type");
        if (valueType == "number" && value != null)
        {
            value = ToDouble(value);
        }

        // Handle select type validation
        if (valueType == "select" && context.Settings.TryGetValue("options", out var optionsObj))
        {
            var options = ParseOptions(optionsObj);
            var valueStr = value?.ToString();

            if (valueStr != null && options.Count > 0 && !options.Contains(valueStr))
            {
                throw new InvalidOperationException(
                    $"Invalid value for select variable {key}: {valueStr}");
            }
        }

        return Task.FromResult(new Dictionary<string, object?>
        {
            ["value"] = value,
            ["data"] = new Dictionary<string, object?> { [key] = value }
        });
    }

    /// <summary>
    /// Output Data node - outputs data from the flow.
    /// </summary>
    private static Task<Dictionary<string, object?>> OutputDataProcessor(NodeProcessContext context)
    {
        var value = context.Inputs.GetValueOrDefault("value");

        return Task.FromResult(new Dictionary<string, object?>
        {
            ["value"] = value
        });
    }

    #region Helper Methods

    private static double ToDouble(object? value)
    {
        return value switch
        {
            null => 0,
            double d => d,
            float f => f,
            int i => i,
            long l => l,
            decimal dec => (double)dec,
            string s when double.TryParse(s, out var parsed) => parsed,
            JsonElement je when je.ValueKind == JsonValueKind.Number => je.GetDouble(),
            JsonElement je when je.ValueKind == JsonValueKind.String &&
                double.TryParse(je.GetString(), out var parsed) => parsed,
            _ => 0
        };
    }

    private static string? GetStringSetting(Dictionary<string, object?> settings, string key)
    {
        if (!settings.TryGetValue(key, out var value))
            return null;

        return value switch
        {
            string s => s,
            JsonElement je when je.ValueKind == JsonValueKind.String => je.GetString(),
            _ => value?.ToString()
        };
    }

    private static List<string> ParseOptions(object? optionsObj)
    {
        var options = new List<string>();

        switch (optionsObj)
        {
            case string str:
                options.AddRange(str.Split(',').Select(o => o.Trim()));
                break;
            case IEnumerable<object> list:
                options.AddRange(list.Select(o => o?.ToString() ?? "").Where(s => !string.IsNullOrEmpty(s)));
                break;
            case JsonElement je when je.ValueKind == JsonValueKind.Array:
                foreach (var item in je.EnumerateArray())
                {
                    var itemStr = item.GetString();
                    if (!string.IsNullOrEmpty(itemStr))
                        options.Add(itemStr);
                }
                break;
            case JsonElement je when je.ValueKind == JsonValueKind.String:
                var str2 = je.GetString();
                if (str2 != null)
                    options.AddRange(str2.Split(',').Select(o => o.Trim()));
                break;
        }

        return options;
    }

    #endregion
}
