using Xunit;
using ZeroWidth.Workbench.Helpers;

namespace ZeroWidth.Workbench.Tests;

public class HelpersTests
{
    [Theory]
    [InlineData("myFunction", "myFunction")]
    [InlineData("my-function", "my_function")]
    [InlineData("my function", "my_function")]
    [InlineData("my.function", "my_function")]
    [InlineData("MyFunction123", "MyFunction123")]
    [InlineData("special@chars!", "special_chars_")]
    public void CreateSafeToolName_ReplacesInvalidChars(string input, string expected)
    {
        var result = WorkbenchEngineHelpers.CreateSafeToolName(input);
        Assert.Equal(expected, result);
    }

    [Theory]
    [InlineData("https://example.com/mcp", true)]
    [InlineData("http://localhost:8080/mcp", true)]
    [InlineData("/local/path", false)]
    [InlineData("ftp://files.com", false)]
    public void IsRemoteMcpTool_DetectsRemoteUrls(string path, bool expected)
    {
        var result = WorkbenchEngineHelpers.IsRemoteMcpTool(path);
        Assert.Equal(expected, result);
    }

    [Theory]
    [InlineData("string", "string")]
    [InlineData("number", "number")]
    [InlineData("boolean", "boolean")]
    [InlineData("array", "array")]
    [InlineData("object", "object")]
    [InlineData("conversation", "array")]
    [InlineData("message", "object")]
    [InlineData("unknown", "string")]
    public void MapTypeToJsonSchema_MapsTypes(string inputType, string expectedSchemaType)
    {
        var result = WorkbenchEngineHelpers.MapTypeToJsonSchema(inputType);
        Assert.Equal(expectedSchemaType, result["type"]);
    }

    [Theory]
    [InlineData("Hello World", "Hello World")]
    [InlineData("  Trimmed  ", "  Trimmed  ")]
    public void ExtractTextFromContent_ExtractsStringContent(string content, string expected)
    {
        var result = WorkbenchEngineHelpers.ExtractTextFromContent(content);
        Assert.Equal(expected, result);
    }

    [Fact]
    public void EnsureList_ConvertsItemToList()
    {
        var single = "item";
        var result = WorkbenchEngineHelpers.EnsureList(single);

        Assert.Single(result);
        Assert.Equal("item", result[0]);
    }

    [Fact]
    public void EnsureList_ReturnsListAsIs()
    {
        var list = new List<object> { "a", "b", "c" };
        var result = WorkbenchEngineHelpers.EnsureList(list);

        Assert.Equal(3, result.Count);
    }

    [Fact]
    public void EnsureList_ReturnsEmptyListForNull()
    {
        var result = WorkbenchEngineHelpers.EnsureList(null);
        Assert.Empty(result);
    }

    [Fact]
    public void DeepMerge_MergesDictionaries()
    {
        var target = new Dictionary<string, object?>
        {
            ["a"] = 1,
            ["b"] = new Dictionary<string, object?> { ["x"] = 10 }
        };

        var source = new Dictionary<string, object?>
        {
            ["b"] = new Dictionary<string, object?> { ["y"] = 20 },
            ["c"] = 3
        };

        var result = WorkbenchEngineHelpers.DeepMerge(target, source);

        Assert.Equal(1, result["a"]);
        Assert.Equal(3, result["c"]);

        var nested = result["b"] as Dictionary<string, object?>;
        Assert.NotNull(nested);
        Assert.Equal(10, nested["x"]);
        Assert.Equal(20, nested["y"]);
    }
}
