using Xunit;
using ZeroWidth.Zv1.Testing;

namespace ZeroWidth.Zv1.Tests;

/// <summary>
/// Flow integration tests using xUnit.
/// </summary>
public class FlowTests
{
    private readonly string _flowsDir;

    public FlowTests()
    {
        // Navigate from test output directory to flows directory
        var currentDir = Directory.GetCurrentDirectory();
        var testProjectDir = FindProjectDir(currentDir, "ZeroWidth.Zv1.Tests");
        _flowsDir = Path.Combine(testProjectDir, "..", "flows");
    }

    private static string FindProjectDir(string startDir, string projectName)
    {
        var current = new DirectoryInfo(startDir);
        while (current != null)
        {
            var csprojPath = Path.Combine(current.FullName, $"{projectName}.csproj");
            if (File.Exists(csprojPath))
            {
                return current.FullName;
            }

            // Check for the flows directory
            var flowsPath = Path.Combine(current.FullName, "tests", "flows");
            if (Directory.Exists(flowsPath))
            {
                return Path.Combine(current.FullName, "tests", "ZeroWidth.Zv1.Tests");
            }

            current = current.Parent;
        }

        return startDir;
    }

    [Fact]
    public async Task AdditionTest_Legacy_ShouldPass()
    {
        var runner = new FlowTestRunner(_flowsDir, debug: false);
        var result = await runner.RunFlowTestAsync("flow.addition.json");

        Assert.True(result.Passed, result.Error ?? "Test failed without error message");
    }

    [Fact]
    public async Task AdditionTest_Zv1_ShouldPass()
    {
        var runner = new FlowTestRunner(_flowsDir, debug: false);
        var result = await runner.RunFlowTestAsync("flow.addition.zv1");

        Assert.True(result.Passed, result.Error ?? "Test failed without error message");
    }

    [Fact]
    public async Task AllFlowTests_ShouldPass()
    {
        var runner = new FlowTestRunner(_flowsDir, debug: false);
        var summary = await runner.RunAllTestsAsync();

        FlowTestRunner.PrintSummary(summary);

        // For now, we expect the simple addition tests to pass
        // Other tests may be skipped due to missing node implementations
        Assert.True(summary.Failed == 0, $"{summary.Failed} test(s) failed");
    }
}
