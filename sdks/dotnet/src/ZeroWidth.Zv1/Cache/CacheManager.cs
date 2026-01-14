using System.Collections.Concurrent;

namespace ZeroWidth.Zv1.Cache;

/// <summary>
/// Represents a cached value with timestamp.
/// </summary>
public record CacheEntry
{
    /// <summary>Gets the cached value.</summary>
    public required object? Value { get; init; }

    /// <summary>Gets the timestamp when the value was cached.</summary>
    public long Timestamp { get; init; } = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
}

/// <summary>
/// Manages cached values for node inputs and outputs during flow execution.
/// Supports value history tracking for refiring inputs.
/// </summary>
public class CacheManager
{
    private readonly ConcurrentDictionary<string, List<CacheEntry>> _cache = new();
    private readonly ConcurrentDictionary<string, long> _consumptionTracking = new();
    private readonly object _lock = new();

    /// <summary>
    /// Sets a value in the cache with timestamp tracking.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <param name="value">The value to cache.</param>
    /// <param name="timestamp">Optional timestamp (defaults to current time).</param>
    public void Set(string key, object? value, long? timestamp = null)
    {
        var entry = new CacheEntry
        {
            Value = value,
            Timestamp = timestamp ?? DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
        };

        _cache.AddOrUpdate(
            key,
            _ => new List<CacheEntry> { entry },
            (_, list) =>
            {
                lock (_lock)
                {
                    list.Add(entry);
                    return list;
                }
            });
    }

    /// <summary>
    /// Gets the most recent value for a key.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <returns>The cached value, or null if not found.</returns>
    public object? Get(string key)
    {
        if (_cache.TryGetValue(key, out var list))
        {
            lock (_lock)
            {
                if (list.Count > 0)
                {
                    return list[^1].Value;
                }
            }
        }
        return null;
    }

    /// <summary>
    /// Gets the most recent value as a specific type.
    /// </summary>
    /// <typeparam name="T">The expected type.</typeparam>
    /// <param name="key">The cache key.</param>
    /// <returns>The cached value, or default if not found or wrong type.</returns>
    public T? Get<T>(string key)
    {
        var value = Get(key);
        if (value is T typedValue)
        {
            return typedValue;
        }
        return default;
    }

    /// <summary>
    /// Gets all values for a key that are newer than the last consumed timestamp.
    /// Used for refiring inputs.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <param name="consumerId">The consumer ID for tracking consumption.</param>
    /// <returns>List of new values since last consumption.</returns>
    public IReadOnlyList<object?> GetNew(string key, string consumerId)
    {
        var trackingKey = $"{consumerId}:{key}";
        var lastConsumed = GetLastConsumed(trackingKey);

        if (!_cache.TryGetValue(key, out var list))
        {
            return Array.Empty<object?>();
        }

        lock (_lock)
        {
            return list
                .Where(e => e.Timestamp > lastConsumed)
                .Select(e => e.Value)
                .ToList()
                .AsReadOnly();
        }
    }

    /// <summary>
    /// Gets the latest timestamp for a key.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <returns>The latest timestamp, or 0 if not found.</returns>
    public long GetLatestTimestamp(string key)
    {
        if (_cache.TryGetValue(key, out var list))
        {
            lock (_lock)
            {
                if (list.Count > 0)
                {
                    return list[^1].Timestamp;
                }
            }
        }
        return 0;
    }

    /// <summary>
    /// Checks if a key exists in the cache.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <returns>True if the key exists.</returns>
    public bool Has(string key)
    {
        if (_cache.TryGetValue(key, out var list))
        {
            lock (_lock)
            {
                return list.Count > 0;
            }
        }
        return false;
    }

    /// <summary>
    /// Checks if there are new values since last consumption.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <param name="consumerId">The consumer ID for tracking.</param>
    /// <returns>True if there are new values.</returns>
    public bool HasNew(string key, string consumerId)
    {
        var trackingKey = $"{consumerId}:{key}";
        var lastConsumed = GetLastConsumed(trackingKey);
        var latestTimestamp = GetLatestTimestamp(key);

        return latestTimestamp > lastConsumed;
    }

    /// <summary>
    /// Gets the full history of values for a key.
    /// </summary>
    /// <param name="key">The cache key.</param>
    /// <returns>List of all cached entries.</returns>
    public IReadOnlyList<CacheEntry> GetHistory(string key)
    {
        if (_cache.TryGetValue(key, out var list))
        {
            lock (_lock)
            {
                return list.ToList().AsReadOnly();
            }
        }
        return Array.Empty<CacheEntry>();
    }

    /// <summary>
    /// Deletes a key from the cache.
    /// </summary>
    /// <param name="key">The cache key to delete.</param>
    /// <returns>True if the key was deleted.</returns>
    public bool Delete(string key)
    {
        return _cache.TryRemove(key, out _);
    }

    /// <summary>
    /// Clears all cached values.
    /// </summary>
    public void Clear()
    {
        _cache.Clear();
        _consumptionTracking.Clear();
    }

    /// <summary>
    /// Gets all cache keys.
    /// </summary>
    public IReadOnlyList<string> Keys => _cache.Keys.ToList().AsReadOnly();

    /// <summary>
    /// Gets the last consumed timestamp for a tracking key.
    /// </summary>
    /// <param name="trackingKey">The tracking key (consumerId:cacheKey).</param>
    /// <returns>The last consumed timestamp, or 0 if never consumed.</returns>
    public long GetLastConsumed(string trackingKey)
    {
        return _consumptionTracking.GetValueOrDefault(trackingKey, 0);
    }

    /// <summary>
    /// Updates the consumption tracking for a key.
    /// </summary>
    /// <param name="trackingKey">The tracking key (consumerId:cacheKey).</param>
    /// <param name="timestamp">The timestamp to record.</param>
    public void UpdateConsumptionTracking(string trackingKey, long timestamp)
    {
        _consumptionTracking.AddOrUpdate(trackingKey, timestamp, (_, _) => timestamp);
    }

    /// <summary>
    /// Gets the total number of entries across all keys.
    /// </summary>
    public int TotalEntries
    {
        get
        {
            lock (_lock)
            {
                return _cache.Values.Sum(list => list.Count);
            }
        }
    }
}
