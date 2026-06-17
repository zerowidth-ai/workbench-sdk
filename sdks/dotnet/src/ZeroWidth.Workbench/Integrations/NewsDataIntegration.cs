using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Web;

namespace ZeroWidth.Workbench.Integrations;

/// <summary>
/// NewsData.io API response.
/// </summary>
public record NewsDataResponse
{
    /// <summary>Gets or sets the status.</summary>
    [JsonPropertyName("status")]
    public string? Status { get; set; }

    /// <summary>Gets or sets the total results.</summary>
    [JsonPropertyName("totalResults")]
    public int TotalResults { get; set; }

    /// <summary>Gets or sets the results.</summary>
    [JsonPropertyName("results")]
    public List<NewsArticle>? Results { get; set; }

    /// <summary>Gets or sets the next page token.</summary>
    [JsonPropertyName("nextPage")]
    public string? NextPage { get; set; }

    /// <summary>Gets or sets any error message.</summary>
    [JsonPropertyName("message")]
    public string? Message { get; set; }
}

/// <summary>
/// Individual news article.
/// </summary>
public record NewsArticle
{
    /// <summary>Gets or sets the article ID.</summary>
    [JsonPropertyName("article_id")]
    public string? ArticleId { get; set; }

    /// <summary>Gets or sets the title.</summary>
    [JsonPropertyName("title")]
    public string? Title { get; set; }

    /// <summary>Gets or sets the link.</summary>
    [JsonPropertyName("link")]
    public string? Link { get; set; }

    /// <summary>Gets or sets the description.</summary>
    [JsonPropertyName("description")]
    public string? Description { get; set; }

    /// <summary>Gets or sets the content.</summary>
    [JsonPropertyName("content")]
    public string? Content { get; set; }

    /// <summary>Gets or sets the publication date.</summary>
    [JsonPropertyName("pubDate")]
    public string? PubDate { get; set; }

    /// <summary>Gets or sets the source ID.</summary>
    [JsonPropertyName("source_id")]
    public string? SourceId { get; set; }

    /// <summary>Gets or sets the creator.</summary>
    [JsonPropertyName("creator")]
    public List<string>? Creator { get; set; }

    /// <summary>Gets or sets the categories.</summary>
    [JsonPropertyName("category")]
    public List<string>? Category { get; set; }

    /// <summary>Gets or sets the country.</summary>
    [JsonPropertyName("country")]
    public List<string>? Country { get; set; }

    /// <summary>Gets or sets the language.</summary>
    [JsonPropertyName("language")]
    public string? Language { get; set; }

    /// <summary>Gets or sets the image URL.</summary>
    [JsonPropertyName("image_url")]
    public string? ImageUrl { get; set; }
}

/// <summary>
/// Integration with NewsData.io API.
/// </summary>
public class NewsDataIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _apiKey;

    /// <summary>
    /// Initializes a new instance of the NewsDataIntegration class.
    /// </summary>
    /// <param name="apiKey">NewsData.io API key.</param>
    /// <param name="timeout">Request timeout.</param>
    public NewsDataIntegration(
        string apiKey,
        TimeSpan? timeout = null)
    {
        _apiKey = apiKey;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri("https://newsdata.io/api/1/"),
            Timeout = timeout ?? TimeSpan.FromSeconds(30)
        };
    }

    /// <summary>
    /// Make a request to any NewsData.io endpoint.
    /// </summary>
    /// <param name="endpoint">The endpoint path.</param>
    /// <param name="parameters">Query parameters.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The API response.</returns>
    public async Task<NewsDataResponse> RequestAsync(
        string endpoint,
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
    {
        var cleanParams = CleanParameters(parameters);
        var processedParams = ProcessParameters(cleanParams);

        // Build query string
        var queryParams = HttpUtility.ParseQueryString(string.Empty);
        queryParams["apikey"] = _apiKey;

        foreach (var (key, value) in processedParams)
        {
            if (value != null)
                queryParams[key] = value.ToString();
        }

        var response = await _httpClient.GetAsync($"{endpoint}?{queryParams}", cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            string errorMessage;

            try
            {
                var errorJson = JsonDocument.Parse(errorContent).RootElement;
                errorMessage = errorJson.TryGetProperty("message", out var msg)
                    ? msg.GetString() ?? "Unknown error"
                    : response.ReasonPhrase ?? "Unknown error";
            }
            catch
            {
                errorMessage = response.ReasonPhrase ?? "Unknown error";
            }

            throw new HttpRequestException(
                $"NewsData API error: {(int)response.StatusCode} - {errorMessage}");
        }

        var result = await response.Content.ReadFromJsonAsync<NewsDataResponse>(
            cancellationToken: cancellationToken);

        return result ?? new NewsDataResponse();
    }

    /// <summary>
    /// Get latest news from the last 48 hours.
    /// </summary>
    public Task<NewsDataResponse> GetLatestAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
        => RequestAsync("latest", parameters, cancellationToken);

    /// <summary>
    /// Get historical news from archive.
    /// </summary>
    public Task<NewsDataResponse> GetArchiveAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
        => RequestAsync("archive", parameters, cancellationToken);

    /// <summary>
    /// Get breaking/real-time news.
    /// </summary>
    public Task<NewsDataResponse> GetBreakingAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
        => RequestAsync("news", parameters, cancellationToken);

    /// <summary>
    /// Get crypto-specific news.
    /// </summary>
    public Task<NewsDataResponse> GetCryptoAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
        => RequestAsync("crypto", parameters, cancellationToken);

    /// <summary>
    /// Get list of source domains.
    /// </summary>
    public Task<NewsDataResponse> GetSourcesAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
        => RequestAsync("sources", parameters, cancellationToken);

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
            if (value is bool b && !b) continue;
            if (value is ICollection<object> collection && collection.Count == 0) continue;

            // Convert true to 1
            if (value is bool bVal && bVal)
            {
                clean[key] = 1;
                continue;
            }

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

        // Parameter name mappings
        var paramMappings = new Dictionary<string, string>
        {
            ["categories"] = "category",
            ["exclude_categories"] = "excludecategory",
            ["countries"] = "country",
            ["regions"] = "region",
            ["languages"] = "language",
            ["domains"] = "domain",
            ["exclude_domains"] = "excludedomain",
            ["exclude_fields"] = "excludefield",
            ["coins"] = "coin"
        };

        foreach (var (inputKey, apiKey) in paramMappings)
        {
            if (processed.TryGetValue(inputKey, out var value))
            {
                processed[apiKey] = value;
                processed.Remove(inputKey);
            }
        }

        // Convert arrays to comma-separated strings
        var arrayFields = new[]
        {
            "country", "region", "category", "excludecategory",
            "language", "domain", "excludedomain", "excludefield", "coin"
        };

        foreach (var field in arrayFields)
        {
            if (processed.TryGetValue(field, out var value))
            {
                var arrayValue = StringToArray(value);
                if (arrayValue.Count > 0)
                {
                    processed[field] = string.Join(",", arrayValue);
                }
            }
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
