using System.Collections.Concurrent;
using System.Text.Json;

namespace ZeroWidth.Zv1.Integrations;

/// <summary>
/// OAuth key structure.
/// </summary>
public class OAuthKey
{
    /// <summary>Gets or sets the access token.</summary>
    public required string AccessToken { get; set; }

    /// <summary>Gets or sets the refresh token.</summary>
    public string? RefreshToken { get; set; }

    /// <summary>Gets or sets when the token expires.</summary>
    public object? ExpiresAt { get; set; }

    /// <summary>Gets or sets the refresh callback.</summary>
    public Func<OAuthRefreshContext, Task<OAuthKey>>? OnRefresh { get; set; }
}

/// <summary>
/// Context passed to OAuth refresh callbacks.
/// </summary>
public record OAuthRefreshContext
{
    /// <summary>Gets the provider name.</summary>
    public required string Provider { get; init; }

    /// <summary>Gets the current access token.</summary>
    public required string CurrentToken { get; init; }

    /// <summary>Gets the refresh token.</summary>
    public string? RefreshToken { get; init; }

    /// <summary>Gets when the token expires.</summary>
    public object? ExpiresAt { get; init; }
}

/// <summary>
/// OAuth refresh event.
/// </summary>
public record OAuthRefreshEvent
{
    /// <summary>Gets the event type.</summary>
    public required string Type { get; init; }

    /// <summary>Gets the provider.</summary>
    public required string Provider { get; init; }

    /// <summary>Gets the timestamp.</summary>
    public long Timestamp { get; init; }

    /// <summary>Gets the event data.</summary>
    public Dictionary<string, object?>? Data { get; init; }
}

/// <summary>
/// OAuth 2.0 Token Refresh Manager.
/// Handles token refresh with coalescing for concurrent requests.
/// </summary>
public class OAuthRefreshManager
{
    private readonly ConcurrentDictionary<string, Task<OAuthKey>> _refreshPromises = new();
    private readonly TimeSpan _expirySkew;
    private readonly int _maxRefreshRetries;
    private readonly TimeSpan _refreshTimeout;
    private readonly Action<OAuthRefreshEvent>? _onNodeUpdate;
    private readonly Dictionary<string, OAuthKey>? _keys;

    /// <summary>
    /// Initializes a new instance of the OAuthRefreshManager class.
    /// </summary>
    /// <param name="expirySkewMs">Milliseconds before expiry to trigger refresh.</param>
    /// <param name="maxRefreshRetries">Maximum retry attempts.</param>
    /// <param name="refreshTimeoutMs">Timeout for refresh requests.</param>
    /// <param name="onNodeUpdate">Callback for refresh events.</param>
    /// <param name="keys">Reference to keys dictionary for updates.</param>
    public OAuthRefreshManager(
        int expirySkewMs = 60000,
        int maxRefreshRetries = 3,
        int refreshTimeoutMs = 20000,
        Action<OAuthRefreshEvent>? onNodeUpdate = null,
        Dictionary<string, OAuthKey>? keys = null)
    {
        _expirySkew = TimeSpan.FromMilliseconds(expirySkewMs);
        _maxRefreshRetries = maxRefreshRetries;
        _refreshTimeout = TimeSpan.FromMilliseconds(refreshTimeoutMs);
        _onNodeUpdate = onNodeUpdate;
        _keys = keys;
    }

    /// <summary>
    /// Check if a key is an OAuth key.
    /// </summary>
    public static bool IsOAuthKey(object? key)
    {
        if (key is OAuthKey oauthKey)
        {
            return !string.IsNullOrEmpty(oauthKey.AccessToken) && oauthKey.OnRefresh != null;
        }

        if (key is JsonElement element && element.ValueKind == JsonValueKind.Object)
        {
            var hasAccessToken = element.TryGetProperty("accessToken", out var at) ||
                                element.TryGetProperty("access_token", out at);
            var hasOnRefresh = element.TryGetProperty("onRefresh", out _) ||
                              element.TryGetProperty("on_refresh", out _);
            return hasAccessToken && hasOnRefresh;
        }

        if (key is IDictionary<string, object?> dict)
        {
            return (dict.ContainsKey("accessToken") || dict.ContainsKey("access_token")) &&
                   (dict.ContainsKey("onRefresh") || dict.ContainsKey("on_refresh"));
        }

        return false;
    }

    /// <summary>
    /// Parse an expires_at value to DateTimeOffset.
    /// </summary>
    public static DateTimeOffset? ParseExpiresAt(object? expiresAt)
    {
        if (expiresAt == null) return null;

        if (expiresAt is long epochMs)
        {
            return DateTimeOffset.FromUnixTimeMilliseconds(epochMs);
        }

        if (expiresAt is int epochInt)
        {
            return DateTimeOffset.FromUnixTimeMilliseconds(epochInt);
        }

        if (expiresAt is string str)
        {
            if (DateTimeOffset.TryParse(str, out var isoDate))
            {
                return isoDate;
            }

            if (long.TryParse(str, out var epochNum))
            {
                return DateTimeOffset.FromUnixTimeMilliseconds(epochNum);
            }
        }

        if (expiresAt is JsonElement element)
        {
            if (element.ValueKind == JsonValueKind.Number)
            {
                return DateTimeOffset.FromUnixTimeMilliseconds(element.GetInt64());
            }

            if (element.ValueKind == JsonValueKind.String)
            {
                var strValue = element.GetString();
                if (DateTimeOffset.TryParse(strValue, out var isoDate))
                {
                    return isoDate;
                }

                if (long.TryParse(strValue, out var epochNum))
                {
                    return DateTimeOffset.FromUnixTimeMilliseconds(epochNum);
                }
            }
        }

        return null;
    }

    /// <summary>
    /// Check if a token is expired or will expire soon.
    /// </summary>
    public bool IsTokenExpired(OAuthKey oauthKey)
    {
        var expiresAt = ParseExpiresAt(oauthKey.ExpiresAt);
        if (!expiresAt.HasValue)
        {
            return false; // No expiry info, assume not expired
        }

        var now = DateTimeOffset.UtcNow;
        var expiryThreshold = expiresAt.Value - _expirySkew;
        return now >= expiryThreshold;
    }

    /// <summary>
    /// Ensure token is valid, refresh if needed.
    /// </summary>
    public async Task<OAuthKey> EnsureValidTokenAsync(string provider, OAuthKey oauthKey)
    {
        if (!IsTokenExpired(oauthKey))
        {
            return oauthKey;
        }

        return await RefreshTokenAsync(provider, oauthKey);
    }

    /// <summary>
    /// Refresh OAuth token with coalescing support.
    /// </summary>
    public async Task<OAuthKey> RefreshTokenAsync(string provider, OAuthKey oauthKey)
    {
        // Check if refresh is already in progress
        if (_refreshPromises.TryGetValue(provider, out var existingRefresh))
        {
            try
            {
                return await existingRefresh;
            }
            catch
            {
                // Fall through to start new refresh
            }
        }

        // Start new refresh
        var refreshTask = PerformRefreshAsync(provider, oauthKey);
        _refreshPromises[provider] = refreshTask;

        try
        {
            return await refreshTask;
        }
        finally
        {
            _refreshPromises.TryRemove(provider, out _);
        }
    }

    private async Task<OAuthKey> PerformRefreshAsync(string provider, OAuthKey oauthKey)
    {
        Exception? lastError = null;
        var retries = 0;

        EmitEvent("oauth_refresh_start", provider, new Dictionary<string, object?>
        {
            ["status"] = "started",
            ["retryAttempt"] = retries
        });

        while (retries <= _maxRefreshRetries)
        {
            try
            {
                if (oauthKey.OnRefresh == null)
                {
                    throw new InvalidOperationException("OAuth key does not have a refresh callback");
                }

                var context = new OAuthRefreshContext
                {
                    Provider = provider,
                    CurrentToken = oauthKey.AccessToken,
                    RefreshToken = oauthKey.RefreshToken,
                    ExpiresAt = oauthKey.ExpiresAt
                };

                using var cts = new CancellationTokenSource(_refreshTimeout);
                var refreshTask = oauthKey.OnRefresh(context);
                var timeoutTask = Task.Delay(Timeout.Infinite, cts.Token);

                var completedTask = await Task.WhenAny(refreshTask, timeoutTask);
                if (completedTask == timeoutTask)
                {
                    throw new TimeoutException($"OAuth refresh timeout after {_refreshTimeout.TotalMilliseconds}ms");
                }

                var updatedKey = await refreshTask;

                if (string.IsNullOrEmpty(updatedKey.AccessToken))
                {
                    throw new InvalidOperationException("onRefresh callback must return an object with AccessToken");
                }

                // Update in-memory keys
                if (_keys != null && _keys.ContainsKey(provider))
                {
                    _keys[provider] = updatedKey;
                }

                EmitEvent("oauth_refresh_complete", provider, new Dictionary<string, object?>
                {
                    ["status"] = "success",
                    ["retryAttempt"] = retries
                });

                return updatedKey;
            }
            catch (Exception ex)
            {
                lastError = ex;
                retries++;

                if (retries <= _maxRefreshRetries)
                {
                    EmitEvent("oauth_refresh_failed", provider, new Dictionary<string, object?>
                    {
                        ["status"] = "failed",
                        ["retryAttempt"] = retries,
                        ["error"] = ex.Message
                    });

                    // Exponential backoff
                    await Task.Delay(Math.Min(100 * (int)Math.Pow(2, retries - 1), 1000));
                }
            }
        }

        EmitEvent("oauth_refresh_complete", provider, new Dictionary<string, object?>
        {
            ["status"] = "failed",
            ["retryAttempt"] = retries - 1,
            ["error"] = lastError?.Message ?? "Unknown error"
        });

        throw new InvalidOperationException(
            $"OAuth refresh failed for provider '{provider}' after {_maxRefreshRetries} retries: {lastError?.Message ?? "Unknown error"}",
            lastError);
    }

    private void EmitEvent(string type, string provider, Dictionary<string, object?>? data)
    {
        _onNodeUpdate?.Invoke(new OAuthRefreshEvent
        {
            Type = type,
            Provider = provider,
            Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            Data = data
        });
    }

    /// <summary>
    /// Check if a response indicates token refresh is needed.
    /// </summary>
    public static bool NeedsRefresh(int statusCode, Func<bool>? providerSpecificCheck = null)
    {
        if (statusCode == 401 || statusCode == 403)
        {
            return true;
        }

        return providerSpecificCheck?.Invoke() ?? false;
    }
}
