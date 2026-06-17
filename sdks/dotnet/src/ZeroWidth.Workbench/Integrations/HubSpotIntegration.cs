using System.Net.Http.Json;
using System.Text.Json;

namespace ZeroWidth.Workbench.Integrations;

/// <summary>
/// Integration with HubSpot API using OAuth authentication.
/// </summary>
public class HubSpotIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;
    private OAuthKey _oauthKey;
    private OAuthRefreshManager? _refreshManager;
    private const string BaseUrl = "https://api.hubapi.com";

    /// <summary>
    /// Initializes a new instance of the HubSpotIntegration class.
    /// </summary>
    /// <param name="oauthKey">OAuth key with access token and refresh callback.</param>
    /// <param name="timeout">Request timeout.</param>
    public HubSpotIntegration(
        OAuthKey oauthKey,
        TimeSpan? timeout = null)
    {
        if (!OAuthRefreshManager.IsOAuthKey(oauthKey))
        {
            throw new ArgumentException(
                "HubSpot integration requires an OAuth key with AccessToken and OnRefresh",
                nameof(oauthKey));
        }

        _oauthKey = oauthKey;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri(BaseUrl),
            Timeout = timeout ?? TimeSpan.FromSeconds(30)
        };
    }

    /// <summary>
    /// Set the OAuth refresh manager.
    /// </summary>
    /// <param name="refreshManager">The refresh manager instance.</param>
    public void SetRefreshManager(OAuthRefreshManager refreshManager)
    {
        _refreshManager = refreshManager;
    }

    /// <summary>
    /// Update OAuth key after refresh.
    /// </summary>
    /// <param name="updatedKey">Updated OAuth key.</param>
    public void UpdateOAuthKey(OAuthKey updatedKey)
    {
        _oauthKey = updatedKey;
    }

    /// <summary>
    /// Make an API request to HubSpot with automatic OAuth token refresh.
    /// </summary>
    /// <param name="method">HTTP method.</param>
    /// <param name="url">API endpoint.</param>
    /// <param name="data">Request body for POST/PUT/PATCH.</param>
    /// <param name="queryParams">Query parameters.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>API response as JsonElement.</returns>
    public async Task<JsonElement> RequestAsync(
        HttpMethod method,
        string url,
        object? data = null,
        Dictionary<string, string>? queryParams = null,
        CancellationToken cancellationToken = default)
    {
        if (_refreshManager == null)
        {
            throw new InvalidOperationException(
                "OAuth refresh manager not initialized. This integration requires engine config context.");
        }

        // Ensure token is valid
        _oauthKey = await _refreshManager.EnsureValidTokenAsync("hubspot", _oauthKey);

        var maxRetries = 2;
        var retries = 0;

        while (retries <= maxRetries)
        {
            try
            {
                var fullUrl = url.StartsWith("http") ? url : $"{BaseUrl}{url}";

                if (queryParams != null && queryParams.Count > 0)
                {
                    var queryString = string.Join("&",
                        queryParams.Select(kvp => $"{Uri.EscapeDataString(kvp.Key)}={Uri.EscapeDataString(kvp.Value)}"));
                    fullUrl = $"{fullUrl}?{queryString}";
                }

                var request = new HttpRequestMessage(method, fullUrl);
                request.Headers.Add("Authorization", $"Bearer {_oauthKey.AccessToken}");

                if (data != null && (method == HttpMethod.Post || method == HttpMethod.Put || method.Method == "PATCH"))
                {
                    request.Content = JsonContent.Create(data);
                }

                var response = await _httpClient.SendAsync(request, cancellationToken);

                // Check if token refresh is needed
                if (NeedsRefresh(response))
                {
                    if (retries < maxRetries)
                    {
                        _oauthKey = await _refreshManager.RefreshTokenAsync("hubspot", _oauthKey);
                        retries++;
                        continue;
                    }

                    throw new HttpRequestException($"HubSpot API error: {(int)response.StatusCode} - Token refresh failed");
                }

                if (!response.IsSuccessStatusCode)
                {
                    var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
                    var errorMessage = ExtractErrorMessage(response, errorContent);
                    throw new HttpRequestException($"HubSpot API error: {(int)response.StatusCode} - {errorMessage}");
                }

                var content = await response.Content.ReadAsStringAsync(cancellationToken);
                return JsonDocument.Parse(content).RootElement;
            }
            catch (HttpRequestException) when (retries < maxRetries)
            {
                // Try refresh on network errors
                try
                {
                    _oauthKey = await _refreshManager.RefreshTokenAsync("hubspot", _oauthKey);
                    retries++;
                }
                catch
                {
                    throw;
                }
            }
        }

        throw new HttpRequestException("HubSpot API request failed");
    }

    /// <summary>
    /// GET request.
    /// </summary>
    public Task<JsonElement> GetAsync(
        string url,
        Dictionary<string, string>? queryParams = null,
        CancellationToken cancellationToken = default)
        => RequestAsync(HttpMethod.Get, url, null, queryParams, cancellationToken);

    /// <summary>
    /// POST request.
    /// </summary>
    public Task<JsonElement> PostAsync(
        string url,
        object? data = null,
        CancellationToken cancellationToken = default)
        => RequestAsync(HttpMethod.Post, url, data, null, cancellationToken);

    /// <summary>
    /// PATCH request.
    /// </summary>
    public Task<JsonElement> PatchAsync(
        string url,
        object? data = null,
        CancellationToken cancellationToken = default)
        => RequestAsync(new HttpMethod("PATCH"), url, data, null, cancellationToken);

    /// <summary>
    /// PUT request.
    /// </summary>
    public Task<JsonElement> PutAsync(
        string url,
        object? data = null,
        CancellationToken cancellationToken = default)
        => RequestAsync(HttpMethod.Put, url, data, null, cancellationToken);

    /// <summary>
    /// DELETE request.
    /// </summary>
    public Task<JsonElement> DeleteAsync(
        string url,
        CancellationToken cancellationToken = default)
        => RequestAsync(HttpMethod.Delete, url, null, null, cancellationToken);

    private static bool NeedsRefresh(HttpResponseMessage response)
    {
        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized ||
            response.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            return true;
        }

        return false;
    }

    private static string ExtractErrorMessage(HttpResponseMessage response, string content)
    {
        try
        {
            var json = JsonDocument.Parse(content).RootElement;

            if (json.TryGetProperty("status", out var status) &&
                status.GetString()?.Equals("error", StringComparison.OrdinalIgnoreCase) == true &&
                json.TryGetProperty("message", out var message))
            {
                return message.GetString() ?? "Unknown error";
            }

            if (json.TryGetProperty("error", out var error))
            {
                if (error.ValueKind == JsonValueKind.String)
                {
                    return error.GetString() ?? "Unknown error";
                }

                if (error.TryGetProperty("message", out var errorMessage))
                {
                    return errorMessage.GetString() ?? "Unknown error";
                }
            }
        }
        catch
        {
            // Fall through to default
        }

        return response.ReasonPhrase ?? "Unknown error";
    }

    /// <summary>
    /// Disposes of the HTTP client.
    /// </summary>
    public ValueTask DisposeAsync()
    {
        _httpClient.Dispose();
        return ValueTask.CompletedTask;
    }
}
