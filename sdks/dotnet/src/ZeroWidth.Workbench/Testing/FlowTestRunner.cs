using System.Text.Json;
using ZeroWidth.Workbench.Loaders;
using ZeroWidth.Workbench.NodeProcessors;

namespace ZeroWidth.Workbench.Testing;

/// <summary>
/// Test case for flow tests.
/// </summary>
public record FlowTestCase
{
    /// <summary>Gets or sets the test file name.</summary>
    public string FileName { get; set; } = "";

    /// <summary>Gets or sets the test description.</summary>
    public string? Description { get; set; }

    /// <summary>Gets or sets the flow definition or path.</summary>
    public object? Flow { get; set; }

    /// <summary>Gets or sets the test inputs.</summary>
    public Dictionary<string, object?> Inputs { get; set; } = new();

    /// <summary>Gets or sets the expected outputs.</summary>
    public Dictionary<string, object?>? Expected { get; set; }

    /// <summary>Gets or sets the expected error type.</summary>
    public string? ExpectedErrorType { get; set; }

    /// <summary>Gets or sets the expected error message.</summary>
    public string? ExpectedErrorMessage { get; set; }
}

/// <summary>
/// Result of a flow test execution.
/// </summary>
public record FlowTestResult
{
    /// <summary>Gets or sets the test file name.</summary>
    public required string FileName { get; init; }

    /// <summary>Gets or sets whether the test passed.</summary>
    public bool Passed { get; set; }

    /// <summary>Gets or sets whether the test was skipped.</summary>
    public bool Skipped { get; set; }

    /// <summary>Gets or sets any error message.</summary>
    public string? Error { get; set; }

    /// <summary>Gets or sets the actual outputs.</summary>
    public Dictionary<string, object?>? ActualOutputs { get; set; }

    /// <summary>Gets or sets the duration.</summary>
    public TimeSpan Duration { get; set; }
}

/// <summary>
/// Summary of flow test results.
/// </summary>
public record FlowTestSummary
{
    /// <summary>Gets the total tests run.</summary>
    public int TotalTests { get; init; }

    /// <summary>Gets the passed count.</summary>
    public int Passed { get; init; }

    /// <summary>Gets the failed count.</summary>
    public int Failed { get; init; }

    /// <summary>Gets the skipped count.</summary>
    public int Skipped { get; init; }

    /// <summary>Gets the list of results.</summary>
    public List<FlowTestResult> Results { get; init; } = new();

    /// <summary>Gets the total duration.</summary>
    public TimeSpan Duration { get; init; }
}

/// <summary>
/// Test runner for flow tests.
/// </summary>
public class FlowTestRunner
{
    private readonly string _flowsDir;
    private readonly Dictionary<string, object?>? _keys;
    private readonly bool _debug;

    /// <summary>
    /// Initializes a new instance of the FlowTestRunner class.
    /// </summary>
    /// <param name="flowsDir">Path to the flows directory.</param>
    /// <param name="keys">API keys for integrations.</param>
    /// <param name="debug">Enable debug logging.</param>
    public FlowTestRunner(string flowsDir, Dictionary<string, object?>? keys = null, bool debug = false)
    {
        _flowsDir = flowsDir;
        _keys = keys;
        _debug = debug;

        // Initialize node processors
        NodeProcessorRegistry.Initialize();
    }

    /// <summary>
    /// Run all flow tests in the directory.
    /// </summary>
    /// <returns>Test summary.</returns>
    public async Task<FlowTestSummary> RunAllTestsAsync()
    {
        var startTime = DateTime.UtcNow;
        var results = new List<FlowTestResult>();

        if (!Directory.Exists(_flowsDir))
        {
            Console.WriteLine($"[ERROR] Flows directory not found: {_flowsDir}");
            return new FlowTestSummary
            {
                TotalTests = 0,
                Passed = 0,
                Failed = 0,
                Skipped = 0,
                Results = results,
                Duration = DateTime.UtcNow - startTime
            };
        }

        // Get all test files (.json and .zwf/.zv1, but not .test.json)
        var testFiles = Directory.GetFiles(_flowsDir)
            .Select(Path.GetFileName)
            .Where(f => f != null &&
                ((f.EndsWith(".json") && !f.EndsWith(".test.json")) || f.EndsWith(".zwf") || f.EndsWith(".zv1")))
            .OrderBy(f => f)
            .ToList();

        Console.WriteLine($"[INFO] Running all flow tests ({testFiles.Count} files)");

        foreach (var testFile in testFiles)
        {
            if (testFile != null)
            {
                var result = await RunFlowTestAsync(testFile);
                results.Add(result);
            }
        }

        return new FlowTestSummary
        {
            TotalTests = results.Count,
            Passed = results.Count(r => r.Passed && !r.Skipped),
            Failed = results.Count(r => !r.Passed && !r.Skipped),
            Skipped = results.Count(r => r.Skipped),
            Results = results,
            Duration = DateTime.UtcNow - startTime
        };
    }

    /// <summary>
    /// Run a single flow test.
    /// </summary>
    /// <param name="testFile">The test file name.</param>
    /// <returns>Test result.</returns>
    public async Task<FlowTestResult> RunFlowTestAsync(string testFile)
    {
        var startTime = DateTime.UtcNow;
        var result = new FlowTestResult { FileName = testFile };

        try
        {
            var testCase = await LoadTestCaseAsync(testFile);

            if (testCase.Flow == null)
            {
                result.Skipped = true;
                result.Error = "No flow found";
                result.Duration = DateTime.UtcNow - startTime;
                Console.WriteLine($"[SKIP] {testFile} - No flow found");
                return result;
            }

            Console.WriteLine($"[INFO] Testing flow: {testFile} with inputs: {JsonSerializer.Serialize(testCase.Inputs)}");

            // Create and run engine
            var options = new WorkbenchOptions
            {
                Flow = testCase.Flow,
                Keys = _keys,
                Debug = _debug
            };

            await using var engine = await WorkbenchEngine.CreateAsync(options);
            var execResult = await engine.RunAsync(testCase.Inputs);

            result.ActualOutputs = execResult.Outputs;

            Console.WriteLine($"  [RESULT] {JsonSerializer.Serialize(new { outputs = execResult.Outputs })}");

            // Check expected error
            if (testCase.ExpectedErrorType != null || testCase.ExpectedErrorMessage != null)
            {
                if (execResult.Success)
                {
                    result.Error = "Expected error but flow succeeded";
                    Console.WriteLine($"  [FAIL] {testFile} - {result.Error}");
                }
                else
                {
                    result.Passed = true;
                    Console.WriteLine($"  [PASS] {testFile} - Error as expected");
                }
            }
            // Check expected outputs
            else if (testCase.Expected != null)
            {
                var (match, mismatch) = CompareOutputs(execResult.Outputs, testCase.Expected);
                result.Passed = match;
                if (!match)
                {
                    result.Error = mismatch;
                    Console.WriteLine($"  [FAIL] {testFile} - {result.Error}");
                }
                else
                {
                    Console.WriteLine($"  [PASS] {testFile}");
                }
            }
            else
            {
                // No expected output defined, just check it ran successfully
                result.Passed = execResult.Success;
                if (!execResult.Success)
                {
                    result.Error = execResult.Errors.FirstOrDefault()?.Message ?? "Unknown error";
                    Console.WriteLine($"  [FAIL] {testFile} - {result.Error}");
                }
                else
                {
                    Console.WriteLine($"  [PASS] {testFile}");
                }
            }
        }
        catch (Exception ex)
        {
            result.Error = ex.Message;
            Console.WriteLine($"  [FAIL] {testFile}");
            Console.WriteLine($"    Error: {ex.Message}");
        }

        result.Duration = DateTime.UtcNow - startTime;
        return result;
    }

    private async Task<FlowTestCase> LoadTestCaseAsync(string testFile)
    {
        var testPath = Path.Combine(_flowsDir, testFile);
        var testCase = new FlowTestCase { FileName = testFile };

        if (testFile.EndsWith(".zwf") || testFile.EndsWith(".zv1"))
        {
            // .zwf (current) / .zv1 (legacy) zip format with companion .test.json
            var testMetadataPath = Path.ChangeExtension(testPath, ".test.json");

            if (!File.Exists(testMetadataPath))
            {
                // No test metadata, return empty case (will be skipped)
                return testCase;
            }

            var metadataJson = await File.ReadAllTextAsync(testMetadataPath);
            var metadata = JsonDocument.Parse(metadataJson).RootElement;

            testCase.Flow = testPath; // Use file path for .zv1 files
            testCase.Description = metadata.TryGetProperty("description", out var desc)
                ? desc.GetString()
                : null;
            testCase.Inputs = metadata.TryGetProperty("inputs", out var inputs)
                ? JsonElementToDictionary(inputs)
                : new Dictionary<string, object?>();
            testCase.Expected = metadata.TryGetProperty("expected", out var expected)
                ? JsonElementToDictionary(expected)
                : null;

            if (metadata.TryGetProperty("expectedError", out var expectedError))
            {
                testCase.ExpectedErrorType = expectedError.TryGetProperty("type", out var errType)
                    ? errType.GetString()
                    : null;
                testCase.ExpectedErrorMessage = expectedError.TryGetProperty("message", out var errMsg)
                    ? errMsg.GetString()
                    : null;
            }
        }
        else if (testFile.EndsWith(".json") && !testFile.EndsWith(".test.json"))
        {
            // Legacy JSON format with embedded flow
            var json = await File.ReadAllTextAsync(testPath);
            var doc = JsonDocument.Parse(json).RootElement;

            if (!doc.TryGetProperty("flow", out var flow))
            {
                // No flow in the file
                return testCase;
            }

            testCase.Flow = flow;
            testCase.Inputs = doc.TryGetProperty("inputs", out var inputs)
                ? JsonElementToDictionary(inputs)
                : new Dictionary<string, object?>();
            testCase.Expected = doc.TryGetProperty("expected", out var expected)
                ? JsonElementToDictionary(expected)
                : null;

            if (doc.TryGetProperty("expectedError", out var expectedError))
            {
                testCase.ExpectedErrorType = expectedError.TryGetProperty("type", out var errType)
                    ? errType.GetString()
                    : null;
                testCase.ExpectedErrorMessage = expectedError.TryGetProperty("message", out var errMsg)
                    ? errMsg.GetString()
                    : null;
            }
        }

        return testCase;
    }

    private static (bool Match, string? Mismatch) CompareOutputs(
        Dictionary<string, object?> actual,
        Dictionary<string, object?> expected)
    {
        foreach (var (key, expectedValue) in expected)
        {
            if (!actual.TryGetValue(key, out var actualValue))
            {
                return (false, $"Missing output: {key}");
            }

            // Handle numeric comparison with tolerance for floating point
            if (IsNumeric(expectedValue) && IsNumeric(actualValue))
            {
                var expectedNum = Convert.ToDouble(expectedValue);
                var actualNum = Convert.ToDouble(actualValue);

                if (Math.Abs(expectedNum - actualNum) > 0.0001)
                {
                    return (false, $"Output mismatch for {key}: expected {expectedNum}, got {actualNum}");
                }
            }
            else
            {
                var expectedJson = JsonSerializer.Serialize(expectedValue);
                var actualJson = JsonSerializer.Serialize(actualValue);

                if (expectedJson != actualJson)
                {
                    return (false, $"Output mismatch for {key}: expected {expectedJson}, got {actualJson}");
                }
            }
        }

        return (true, null);
    }

    private static bool IsNumeric(object? value)
    {
        return value is int or long or float or double or decimal or
            (value is JsonElement je && je.ValueKind == JsonValueKind.Number);
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
    /// Print test summary to console.
    /// </summary>
    public static void PrintSummary(FlowTestSummary summary)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 60));
        Console.WriteLine("FLOW TEST SUMMARY");
        Console.WriteLine(new string('=', 60));
        Console.WriteLine($"Total tests: {summary.TotalTests}");
        Console.WriteLine($"Passed: {summary.Passed}");
        Console.WriteLine($"Failed: {summary.Failed}");
        Console.WriteLine($"Skipped: {summary.Skipped}");

        if (summary.Failed > 0)
        {
            Console.WriteLine();
            Console.WriteLine("FAILED TESTS:");
            Console.WriteLine(new string('-', 40));

            foreach (var result in summary.Results.Where(r => !r.Passed && !r.Skipped))
            {
                Console.WriteLine($"{result.FileName}: {result.Error}");
            }

            Console.WriteLine();
            Console.WriteLine($"X {summary.Failed} test(s) failed!");
        }
        else
        {
            Console.WriteLine();
            Console.WriteLine("All tests passed!");
        }
    }
}
