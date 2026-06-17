using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Web;

namespace ZeroWidth.Workbench.Integrations;

/// <summary>
/// Google Custom Search response.
/// </summary>
public record GoogleSearchResponse
{
    /// <summary>Gets or sets the search items.</summary>
    [JsonPropertyName("items")]
    public List<GoogleSearchItem>? Items { get; set; }

    /// <summary>Gets or sets the search information.</summary>
    [JsonPropertyName("searchInformation")]
    public GoogleSearchInfo? SearchInformation { get; set; }
}

/// <summary>
/// Individual search result item.
/// </summary>
public record GoogleSearchItem
{
    /// <summary>Gets or sets the title.</summary>
    [JsonPropertyName("title")]
    public string? Title { get; set; }

    /// <summary>Gets or sets the link.</summary>
    [JsonPropertyName("link")]
    public string? Link { get; set; }

    /// <summary>Gets or sets the snippet.</summary>
    [JsonPropertyName("snippet")]
    public string? Snippet { get; set; }

    /// <summary>Gets or sets the display link.</summary>
    [JsonPropertyName("displayLink")]
    public string? DisplayLink { get; set; }
}

/// <summary>
/// Search information metadata.
/// </summary>
public record GoogleSearchInfo
{
    /// <summary>Gets or sets the total results.</summary>
    [JsonPropertyName("totalResults")]
    public string? TotalResults { get; set; }

    /// <summary>Gets or sets the search time.</summary>
    [JsonPropertyName("searchTime")]
    public double SearchTime { get; set; }
}

/// <summary>
/// Integration with Google Custom Search API.
/// </summary>
public class GoogleCustomSearchIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _apiKey;
    private readonly string _cx;

    /// <summary>
    /// Initializes a new instance of the GoogleCustomSearchIntegration class.
    /// </summary>
    /// <param name="apiKey">Google API key.</param>
    /// <param name="cx">Custom Search Engine ID.</param>
    /// <param name="timeout">Request timeout.</param>
    public GoogleCustomSearchIntegration(
        string apiKey,
        string cx,
        TimeSpan? timeout = null)
    {
        _apiKey = apiKey ?? throw new ArgumentNullException(nameof(apiKey), "Google Custom Search API key is required");
        _cx = cx;

        _httpClient = new HttpClient
        {
            BaseAddress = new Uri("https://www.googleapis.com/customsearch/v1"),
            Timeout = timeout ?? TimeSpan.FromSeconds(30)
        };
    }

    /// <summary>
    /// Initializes from a key object containing key and cx properties.
    /// </summary>
    /// <param name="keyObject">Object with key and cx properties.</param>
    /// <param name="timeout">Request timeout.</param>
    public GoogleCustomSearchIntegration(
        Dictionary<string, string> keyObject,
        TimeSpan? timeout = null)
        : this(
            keyObject.TryGetValue("key", out var key) ? key : throw new ArgumentException("key is required"),
            keyObject.TryGetValue("cx", out var cx) ? cx : "",
            timeout)
    {
    }

    /// <summary>
    /// Perform a custom search.
    /// </summary>
    /// <param name="parameters">Search parameters.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The search response.</returns>
    public async Task<GoogleSearchResponse> SearchAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
    {
        var cleanParams = CleanParameters(parameters);
        var processedParams = ProcessParameters(cleanParams);

        // Build query string
        var queryParams = HttpUtility.ParseQueryString(string.Empty);
        queryParams["key"] = _apiKey;

        if (!string.IsNullOrEmpty(_cx))
            queryParams["cx"] = _cx;

        foreach (var (key, value) in processedParams)
        {
            if (value != null)
                queryParams[key] = value.ToString();
        }

        var response = await _httpClient.GetAsync($"?{queryParams}", cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            string errorMessage;

            try
            {
                var errorJson = JsonDocument.Parse(errorContent).RootElement;
                if (errorJson.TryGetProperty("error", out var error))
                {
                    errorMessage = error.TryGetProperty("message", out var msg)
                        ? msg.GetString() ?? "Unknown error"
                        : "Unknown error";
                }
                else
                {
                    errorMessage = response.ReasonPhrase ?? "Unknown error";
                }
            }
            catch
            {
                errorMessage = response.ReasonPhrase ?? "Unknown error";
            }

            throw new HttpRequestException(
                $"Google Custom Search API error: {(int)response.StatusCode} - {errorMessage}");
        }

        var result = await response.Content.ReadFromJsonAsync<GoogleSearchResponse>(
            cancellationToken: cancellationToken);

        return result ?? new GoogleSearchResponse();
    }

    /// <summary>
    /// Remove null, empty, or invalid parameters.
    /// </summary>
    private static Dictionary<string, object?> CleanParameters(Dictionary<string, object?> parameters)
    {
        var clean = new Dictionary<string, object?>();

        foreach (var (key, value) in parameters)
        {
            if (value == null) continue;
            if (value is string str && string.IsNullOrEmpty(str)) continue;
            if (value is ICollection<object> collection && collection.Count == 0) continue;

            clean[key] = value;
        }

        return clean;
    }

    /// <summary>
    /// Process parameters with name mappings and type conversions.
    /// </summary>
    public static Dictionary<string, object?> ProcessParameters(Dictionary<string, object?> parameters)
    {
        var processed = new Dictionary<string, object?>(parameters);

        // Convert arrays to space-separated strings for API
        var arrayFields = new[] { "excludeTerms", "fileType", "rights", "safe" };
        foreach (var field in arrayFields)
        {
            if (processed.TryGetValue(field, out var value))
            {
                var arrayValue = StringToArray(value);
                if (arrayValue.Count > 0)
                {
                    processed[field] = string.Join(" ", arrayValue);
                }
            }
        }

        // Only include searchType if it's "image"
        if (processed.TryGetValue("searchType", out var searchType) &&
            searchType?.ToString() != "image")
        {
            processed.Remove("searchType");
        }

        return processed;
    }

    /// <summary>
    /// Convert a comma-separated string to an array.
    /// </summary>
    public static List<string> StringToArray(object? input)
    {
        if (input is IEnumerable<string> enumerable)
            return enumerable.ToList();

        if (input is string str)
        {
            return str.Split(',')
                .Select(item => item.Trim())
                .Where(item => !string.IsNullOrEmpty(item))
                .ToList();
        }

        return new List<string>();
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
