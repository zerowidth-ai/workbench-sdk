using Xunit;
using ZeroWidth.Zv1.Cache;

namespace ZeroWidth.Zv1.Tests;

public class CacheManagerTests
{
    [Fact]
    public void Set_SetsValue()
    {
        var cache = new CacheManager();
        cache.Set("test", "value");

        Assert.True(cache.Has("test"));
        Assert.Equal("value", cache.Get<string>("test"));
    }

    [Fact]
    public void Get_ReturnsNull_WhenKeyNotExists()
    {
        var cache = new CacheManager();
        var result = cache.Get<string>("nonexistent");

        Assert.Null(result);
    }

    [Fact]
    public void GetNew_ReturnsValue_WhenNotConsumed()
    {
        var cache = new CacheManager();
        cache.Set("test", "value");

        Assert.True(cache.HasNew("test"));
        var result = cache.GetNew<string>("test");
        Assert.Equal("value", result);
    }

    [Fact]
    public void GetNew_ReturnsNull_AfterConsumed()
    {
        var cache = new CacheManager();
        cache.Set("test", "value");

        cache.GetNew<string>("test"); // Consume
        var result = cache.GetNew<string>("test");

        Assert.Null(result);
    }

    [Fact]
    public void HasNew_ReturnsFalse_AfterConsumed()
    {
        var cache = new CacheManager();
        cache.Set("test", "value");

        cache.GetNew<string>("test");

        Assert.False(cache.HasNew("test"));
    }

    [Fact]
    public void Delete_RemovesKey()
    {
        var cache = new CacheManager();
        cache.Set("test", "value");
        cache.Delete("test");

        Assert.False(cache.Has("test"));
    }

    [Fact]
    public void Clear_RemovesAllKeys()
    {
        var cache = new CacheManager();
        cache.Set("key1", "value1");
        cache.Set("key2", "value2");
        cache.Clear();

        Assert.False(cache.Has("key1"));
        Assert.False(cache.Has("key2"));
    }

    [Fact]
    public void GetHistory_ReturnsAllValues()
    {
        var cache = new CacheManager();
        cache.Set("test", "value1");
        cache.Set("test", "value2");
        cache.Set("test", "value3");

        var history = cache.GetHistory("test");

        Assert.Equal(3, history.Count);
    }
}
