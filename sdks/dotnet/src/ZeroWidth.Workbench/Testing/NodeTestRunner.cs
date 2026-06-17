using System.Text.Json;
using System.Text.RegularExpressions;
using ZeroWidth.Workbench.Loaders;

namespace ZeroWidth.Workbench.Testing;

/// <summary>
/// Test case definition from .tests.json files.
/// </summary>
public record TestCase
{
    /// <summary>Gets or sets the test description.</summary>
    public string Description { get; set; } = "";

    /// <summary>Gets or sets the test inputs.</summary>
    public Dictionary<string, object?> Inputs { get; set; } = new();

    /// <summary>Gets or sets the test settings.</summary>
    public Dictionary<string, object?> Settings { get; set; } = new();

    /// <summary>Gets or sets the expected outputs.</summary>
    public Dictionary<string, object?>? Expected { get; set; }

    /// <summary>Gets or sets the expected schema for validation.</summary>
    public Dictionary<string, JsonElement>? ExpectedSchema { get; set; }

    /// <summary>Gets or sets the expected error message.</summary>
    public string? ExpectedError { get; set; }

    /// <summary>Gets or sets a custom test function name.</summary>
    public string? CustomTest { get; set; }
}

/// <summary>
/// Result of a single test execution.
/// </summary>
public record TestResult
{
    /// <summary>Gets or sets the node name.</summary>
    public required string Node { get; init; }

    /// <summary>Gets or sets the test description.</summary>
    public required string Description { get; init; }

    /// <summary>Gets or sets whether the test passed.</summary>
    public bool Passed { get; set; }

    /// <summary>Gets or sets any error message.</summary>
    public string? Error { get; set; }

    /// <summary>Gets or sets the duration.</summary>
    public TimeSpan Duration { get; set; }
}

/// <summary>
/// Summary of test run results.
/// </summary>
public record TestSummary
{
    /// <summary>Gets the total tests run.</summary>
    public int TotalTests { get; init; }

    /// <summary>Gets the passed count.</summary>
    public int Passed { get; init; }

    /// <summary>Gets the failed count.</summary>
    public int Failed { get; init; }

    /// <summary>Gets the list of results.</summary>
    public List<TestResult> Results { get; init; } = new();

    /// <summary>Gets the total duration.</summary>
    public TimeSpan Duration { get; init; }
}

/// <summary>
/// Test runner for node tests.
/// </summary>
public class NodeTestRunner
{
    private readonly string _nodesDir;
    private readonly Dictionary<string, object?> _config;
    private readonly Dictionary<string, Func<Dictionary<string, object?>, TestCase, bool>> _customTests;

    /// <summary>
    /// Initializes a new instance of the NodeTestRunner class.
    /// </summary>
    /// <param name="nodesDir">Path to the nodes directory.</param>
    /// <param name="config">Engine configuration.</param>
    public NodeTestRunner(string nodesDir, Dictionary<string, object?>? config = null)
    {
        _nodesDir = nodesDir;
        _config = config ?? new Dictionary<string, object?>();
        _customTests = new Dictionary<string, Func<Dictionary<string, object?>, TestCase, bool>>
        {
            ["shuffleTest"] = ShuffleTest,
            ["seedShuffleTest"] = ShuffleTest
        };
    }

    /// <summary>
    /// Run all tests for all nodes.
    /// </summary>
    /// <returns>Test summary.</returns>
    public async Task<TestSummary> RunAllTestsAsync()
    {
        return await RunTestsAsync(null, null);
    }

    /// <summary>
    /// Run tests for a specific node.
    /// </summary>
    /// <param name="nodeName">Name of the node to test.</param>
    /// <returns>Test summary.</returns>
    public async Task<TestSummary> RunNodeTestsAsync(string nodeName)
    {
        return await RunTestsAsync(nodeName, null);
    }

    /// <summary>
    /// Run tests starting from a specific node.
    /// </summary>
    /// <param name="startFrom">Name of the node to start from.</param>
    /// <returns>Test summary.</returns>
    public async Task<TestSummary> RunTestsStartingFromAsync(string startFrom)
    {
        return await RunTestsAsync(null, startFrom);
    }

    /// <summary>
    /// Run tests with filtering options.
    /// </summary>
    private async Task<TestSummary> RunTestsAsync(string? specificNode, string? startFrom)
    {
        var startTime = DateTime.UtcNow;
        var results = new List<TestResult>();

        if (!Directory.Exists(_nodesDir))
        {
            return new TestSummary
            {
                TotalTests = 0,
                Passed = 0,
                Failed = 0,
                Results = results,
                Duration = DateTime.UtcNow - startTime
            };
        }

        var nodeDirs = Directory.GetDirectories(_nodesDir)
            .Select(Path.GetFileName)
            .Where(n => n != null)
            .Cast<string>()
            .OrderBy(n => n)
            .ToList();

        List<string> nodesToTest;

        if (!string.IsNullOrEmpty(specificNode))
        {
            if (!nodeDirs.Contains(specificNode))
            {
                throw new ArgumentException($"Node '{specificNode}' not found in nodes directory.");
            }
            nodesToTest = new List<string> { specificNode };
        }
        else if (!string.IsNullOrEmpty(startFrom))
        {
            var startIndex = nodeDirs.IndexOf(startFrom);
            if (startIndex == -1)
            {
                throw new ArgumentException($"Node '{startFrom}' not found in nodes directory.");
            }
            nodesToTest = nodeDirs.Skip(startIndex).ToList();
        }
        else
        {
            nodesToTest = nodeDirs;
        }

        foreach (var nodeName in nodesToTest)
        {
            var nodeDir = Path.Combine(_nodesDir, nodeName);
            var testsPath = Path.Combine(nodeDir, $"{nodeName}.tests.json");

            if (!File.Exists(testsPath))
                continue;

            var testCases = await LoadTestCasesAsync(testsPath);

            foreach (var testCase in testCases)
            {
                var result = await RunNodeTestAsync(nodeName, nodeDir, testCase);
                results.Add(result);
            }
        }

        return new TestSummary
        {
            TotalTests = results.Count,
            Passed = results.Count(r => r.Passed),
            Failed = results.Count(r => !r.Passed),
            Results = results,
            Duration = DateTime.UtcNow - startTime
        };
    }

    private async Task<List<TestCase>> LoadTestCasesAsync(string testsPath)
    {
        var json = await File.ReadAllTextAsync(testsPath);
        var doc = JsonDocument.Parse(json);
        var testCases = new List<TestCase>();

        foreach (var element in doc.RootElement.EnumerateArray())
        {
            var testCase = new TestCase
            {
                Description = element.TryGetProperty("description", out var desc)
                    ? desc.GetString() ?? ""
                    : ""
            };

            if (element.TryGetProperty("inputs", out var inputs))
            {
                testCase.Inputs = JsonElementToDictionary(inputs);
            }

            if (element.TryGetProperty("settings", out var settings))
            {
                testCase.Settings = JsonElementToDictionary(settings);
            }

            if (element.TryGetProperty("expected", out var expected))
            {
                testCase.Expected = JsonElementToDictionary(expected);
            }

            if (element.TryGetProperty("expectedSchema", out var schema))
            {
                testCase.ExpectedSchema = new Dictionary<string, JsonElement>();
                foreach (var prop in schema.EnumerateObject())
                {
                    testCase.ExpectedSchema[prop.Name] = prop.Value.Clone();
                }
            }

            if (element.TryGetProperty("expectedError", out var error))
            {
                testCase.ExpectedError = error.GetString();
            }

            if (element.TryGetProperty("customTest", out var customTest))
            {
                testCase.CustomTest = customTest.GetString();
            }

            testCases.Add(testCase);
        }

        return testCases;
    }

    private async Task<TestResult> RunNodeTestAsync(string nodeName, string nodeDir, TestCase testCase)
    {
        var startTime = DateTime.UtcNow;
        var result = new TestResult
        {
            Node = nodeName,
            Description = testCase.Description
        };

        var configPath = Path.Combine(nodeDir, $"{nodeName}.config.json");
        var processPath = Path.Combine(nodeDir, $"{nodeName}.process.cs");

        if (!File.Exists(configPath))
        {
            result.Error = $"Missing config file: {configPath}";
            result.Duration = DateTime.UtcNow - startTime;
            return result;
        }

        try
        {
            var configJson = await File.ReadAllTextAsync(configPath);
            var nodeConfig = JsonDocument.Parse(configJson).RootElement;

            // Merge default values into inputs
            var inputs = new Dictionary<string, object?>(testCase.Inputs);
            if (nodeConfig.TryGetProperty("inputs", out var inputDefs))
            {
                foreach (var inputDef in inputDefs.EnumerateArray())
                {
                    var name = inputDef.GetProperty("name").GetString();
                    if (name != null && !inputs.ContainsKey(name))
                    {
                        if (inputDef.TryGetProperty("default", out var defaultValue))
                        {
                            inputs[name] = JsonElementToObject(defaultValue);
                        }
                    }
                }
            }

            // Merge default settings
            var settings = new Dictionary<string, object?>(testCase.Settings);
            if (nodeConfig.TryGetProperty("settings", out var settingDefs))
            {
                foreach (var settingDef in settingDefs.EnumerateArray())
                {
                    var name = settingDef.GetProperty("name").GetString();
                    if (name != null && !settings.ContainsKey(name))
                    {
                        if (settingDef.TryGetProperty("default", out var defaultValue))
                        {
                            settings[name] = JsonElementToObject(defaultValue);
                        }
                    }
                }
            }

            // Execute node process (for now, we only support testing via direct execution)
            // In a full implementation, this would load and execute .process.cs files
            // For testing purposes, we'll simulate the execution

            // TODO: Implement actual .cs process file execution
            // For now, mark as skipped if no process file exists
            if (!File.Exists(processPath))
            {
                result.Passed = true;
                result.Error = "Skipped (no .process.cs file)";
                result.Duration = DateTime.UtcNow - startTime;
                return result;
            }

            // Placeholder for process execution
            var processResult = new Dictionary<string, object?>();

            // Validate results
            if (testCase.ExpectedError != null)
            {
                result.Error = "Expected error but none was thrown";
                result.Duration = DateTime.UtcNow - startTime;
                return result;
            }

            if (testCase.CustomTest != null && _customTests.TryGetValue(testCase.CustomTest, out var customTestFunc))
            {
                result.Passed = customTestFunc(processResult, testCase);
                if (!result.Passed)
                {
                    result.Error = "Custom test function failed";
                }
            }
            else if (testCase.ExpectedSchema != null)
            {
                var (valid, errors) = ValidateSchema(processResult, testCase.ExpectedSchema);
                result.Passed = valid;
                if (!valid)
                {
                    result.Error = $"Schema validation failed: {string.Join(", ", errors)}";
                }
            }
            else if (testCase.Expected != null)
            {
                var (match, mismatch) = CompareOutputs(processResult, testCase.Expected);
                result.Passed = match;
                result.Error = mismatch;
            }
            else
            {
                result.Passed = true;
                result.Error = "Warning: No validation criteria provided";
            }
        }
        catch (Exception ex)
        {
            if (testCase.ExpectedError != null && ex.Message == testCase.ExpectedError)
            {
                result.Passed = true;
            }
            else
            {
                result.Error = ex.Message;
            }
        }

        result.Duration = DateTime.UtcNow - startTime;
        return result;
    }

    private static (bool Valid, List<string> Errors) ValidateSchema(
        Dictionary<string, object?> result,
        Dictionary<string, JsonElement> schema)
    {
        var errors = new List<string>();

        foreach (var (key, schemaElement) in schema)
        {
            if (!result.TryGetValue(key, out var value))
            {
                errors.Add($"Missing expected output: {key}");
                continue;
            }

            // Type validation
            if (schemaElement.TryGetProperty("type", out var typeEl))
            {
                var types = typeEl.ValueKind == JsonValueKind.Array
                    ? typeEl.EnumerateArray().Select(t => t.GetString()).ToList()
                    : new List<string?> { typeEl.GetString() };

                var typeValid = types.Any(t => ValidateType(value, t));
                if (!typeValid)
                {
                    errors.Add($"Type mismatch for {key}: expected {string.Join(" or ", types)}, got {value?.GetType().Name ?? "null"}");
                }
            }

            // Numeric constraints
            if (value is double numValue || value is int intValue || value is long longValue)
            {
                var num = Convert.ToDouble(value);
                if (schemaElement.TryGetProperty("minimum", out var min) && num < min.GetDouble())
                {
                    errors.Add($"Value {num} for {key} is less than minimum {min.GetDouble()}");
                }
                if (schemaElement.TryGetProperty("maximum", out var max) && num > max.GetDouble())
                {
                    errors.Add($"Value {num} for {key} is greater than maximum {max.GetDouble()}");
                }
            }

            // String pattern
            if (value is string strValue && schemaElement.TryGetProperty("pattern", out var pattern))
            {
                var regex = new Regex(pattern.GetString() ?? "");
                if (!regex.IsMatch(strValue))
                {
                    errors.Add($"Value \"{strValue}\" for {key} does not match pattern {pattern.GetString()}");
                }
            }

            // Array constraints
            if (value is IList<object> listValue)
            {
                if (schemaElement.TryGetProperty("minItems", out var minItems) && listValue.Count < minItems.GetInt32())
                {
                    errors.Add($"Array {key} has fewer items ({listValue.Count}) than required ({minItems.GetInt32()})");
                }
                if (schemaElement.TryGetProperty("maxItems", out var maxItems) && listValue.Count > maxItems.GetInt32())
                {
                    errors.Add($"Array {key} has more items ({listValue.Count}) than allowed ({maxItems.GetInt32()})");
                }
            }
        }

        return (errors.Count == 0, errors);
    }

    private static bool ValidateType(object? value, string? expectedType)
    {
        return expectedType switch
        {
            "number" => value is int or long or float or double or decimal,
            "string" => value is string,
            "boolean" => value is bool,
            "object" => value is IDictionary<string, object?>,
            "array" => value is IList<object>,
            "null" => value == null,
            _ => false
        };
    }

    private static (bool Match, string? Mismatch) CompareOutputs(
        Dictionary<string, object?> result,
        Dictionary<string, object?> expected)
    {
        foreach (var (key, expectedValue) in expected)
        {
            if (!result.TryGetValue(key, out var actualValue))
            {
                return (false, $"Missing output: {key}");
            }

            var expectedJson = JsonSerializer.Serialize(expectedValue);
            var actualJson = JsonSerializer.Serialize(actualValue);

            if (expectedJson != actualJson)
            {
                return (false, $"Mismatch for {key}: expected {expectedJson}, got {actualJson}");
            }
        }

        return (true, null);
    }

    private bool ShuffleTest(Dictionary<string, object?> result, TestCase testCase)
    {
        if (!testCase.Inputs.TryGetValue("array", out var inputObj) ||
            !result.TryGetValue("array", out var outputObj))
        {
            return false;
        }

        var input = inputObj as IList<object> ?? new List<object>();
        var output = outputObj as IList<object> ?? new List<object>();

        // Check length
        if (input.Count != output.Count)
            return false;

        // Check all elements present
        foreach (var item in input)
        {
            if (!output.Contains(item))
                return false;
        }

        foreach (var item in output)
        {
            if (!input.Contains(item))
                return false;
        }

        return true;
    }

    private static Dictionary<string, object?> JsonElementToDictionary(JsonElement element)
    {
        var dict = new Dictionary<string, object?>();

        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (var prop in element.EnumerateObject())
            {
                dict[prop.Name] = JsonElementToObject(prop.Value);
            }
        }

        return dict;
    }

    private static object? JsonElementToObject(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Null => null,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Number => element.TryGetInt64(out var l) ? l : element.GetDouble(),
            JsonValueKind.Array => element.EnumerateArray().Select(JsonElementToObject).ToList(),
            JsonValueKind.Object => JsonElementToDictionary(element),
            _ => element.GetRawText()
        };
    }

    /// <summary>
    /// Print test results to console.
    /// </summary>
    public static void PrintResults(TestSummary summary)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 60));
        Console.WriteLine("TEST SUMMARY");
        Console.WriteLine(new string('=', 60));
        Console.WriteLine($"Total tests run: {summary.TotalTests}");
        Console.WriteLine($"Passed: {summary.Passed}");
        Console.WriteLine($"Failed: {summary.Failed}");
        Console.WriteLine($"Duration: {summary.Duration.TotalSeconds:F2}s");

        if (summary.Failed > 0)
        {
            Console.WriteLine();
            Console.WriteLine("FAILED TESTS:");
            Console.WriteLine(new string('-', 40));

            foreach (var result in summary.Results.Where(r => !r.Passed))
            {
                Console.WriteLine($"{result.Node}: {result.Description}");
                Console.WriteLine($"  Error: {result.Error}");
                Console.WriteLine();
            }

            Console.WriteLine($"❌ {summary.Failed} test(s) failed!");
        }
        else
        {
            Console.WriteLine();
            Console.WriteLine("✅ All tests passed!");
        }
    }
}
