using System.Text.Json;
using Xunit;
using ZeroWidth.Zv1.Types;

namespace ZeroWidth.Zv1.Tests;

public class TypeSystemTests
{
    [Theory]
    [InlineData("any", null, true)]
    [InlineData("any", "string", true)]
    [InlineData("any", 123, true)]
    [InlineData("string", "hello", true)]
    [InlineData("string", 123, false)]
    [InlineData("number", 123, true)]
    [InlineData("number", 123.45, true)]
    [InlineData("number", "123", false)]
    [InlineData("boolean", true, true)]
    [InlineData("boolean", false, true)]
    [InlineData("boolean", "true", false)]
    [InlineData("integer", 123, true)]
    [InlineData("integer", 123.45, false)]
    public void TypeCheck_ValidatesBasicTypes(string typeStr, object? value, bool expected)
    {
        var result = TypeSystem.TypeCheck(value, typeStr);
        Assert.Equal(expected, result);
    }

    [Fact]
    public void TypeCheck_ValidatesUnionTypes()
    {
        Assert.True(TypeSystem.TypeCheck("hello", "string or number"));
        Assert.True(TypeSystem.TypeCheck(123, "string or number"));
        Assert.False(TypeSystem.TypeCheck(true, "string or number"));
    }

    [Fact]
    public void TypeCheck_ValidatesArrayType()
    {
        var list = new List<object> { "a", "b", "c" };
        Assert.True(TypeSystem.TypeCheck(list, "array"));
    }

    [Fact]
    public void TypeCheck_ValidatesObjectType()
    {
        var dict = new Dictionary<string, object?> { ["key"] = "value" };
        Assert.True(TypeSystem.TypeCheck(dict, "object"));
    }

    [Fact]
    public void TypeCheck_NullPassesAllTypes()
    {
        Assert.True(TypeSystem.TypeCheck(null, "string"));
        Assert.True(TypeSystem.TypeCheck(null, "number"));
        Assert.True(TypeSystem.TypeCheck(null, "boolean"));
    }

    [Fact]
    public void ConversationToString_FormatsMessages()
    {
        var messages = new List<object>
        {
            new Dictionary<string, object?> { ["role"] = "user", ["content"] = "Hello" },
            new Dictionary<string, object?> { ["role"] = "assistant", ["content"] = "Hi there!" }
        };

        var result = TypeSystem.ConversationToString(messages);

        Assert.Contains("user: Hello", result);
        Assert.Contains("assistant: Hi there!", result);
    }

    [Fact]
    public void MessageToString_FormatsMessage()
    {
        var message = new Dictionary<string, object?> { ["role"] = "user", ["content"] = "Hello" };

        var result = TypeSystem.MessageToString(message);

        Assert.Equal("user: Hello", result);
    }

    [Fact]
    public void TypeCheck_WithJsonElement_String()
    {
        var json = JsonDocument.Parse("\"hello\"").RootElement;
        Assert.True(TypeSystem.TypeCheck(json, "string"));
        Assert.False(TypeSystem.TypeCheck(json, "number"));
    }

    [Fact]
    public void TypeCheck_WithJsonElement_Number()
    {
        var json = JsonDocument.Parse("123").RootElement;
        Assert.True(TypeSystem.TypeCheck(json, "number"));
        Assert.False(TypeSystem.TypeCheck(json, "string"));
    }

    [Fact]
    public void TypeCheck_WithJsonElement_Boolean()
    {
        var jsonTrue = JsonDocument.Parse("true").RootElement;
        var jsonFalse = JsonDocument.Parse("false").RootElement;

        Assert.True(TypeSystem.TypeCheck(jsonTrue, "boolean"));
        Assert.True(TypeSystem.TypeCheck(jsonFalse, "boolean"));
    }

    [Fact]
    public void TypeCheck_WithJsonElement_Array()
    {
        var json = JsonDocument.Parse("[1, 2, 3]").RootElement;
        Assert.True(TypeSystem.TypeCheck(json, "array"));
    }

    [Fact]
    public void TypeCheck_WithJsonElement_Object()
    {
        var json = JsonDocument.Parse("{\"key\": \"value\"}").RootElement;
        Assert.True(TypeSystem.TypeCheck(json, "object"));
    }
}
