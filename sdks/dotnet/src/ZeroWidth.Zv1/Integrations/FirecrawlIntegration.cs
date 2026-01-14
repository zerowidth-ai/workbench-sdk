using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ZeroWidth.Zv1.Integrations;

/// <summary>
/// Firecrawl scrape response.
/// </summary>
public record FirecrawlScrapeResponse
{
    /// <summary>Gets or sets whether the scrape was successful.</summary>
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    /// <summary>Gets or sets the scraped data.</summary>
    [JsonPropertyName("data")]
    public JsonElement? Data { get; set; }

    /// <summary>Gets or sets any error message.</summary>
    [JsonPropertyName("error")]
    public string? Error { get; set; }
}

/// <summary>
/// Integration with Firecrawl's web scraping API.
/// </summary>
public class FirecrawlIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;

    /// <summary>
    /// Initializes a new instance of the FirecrawlIntegration class.
    /// </summary>
    /// <param name="apiKey">Firecrawl API key.</param>
    /// <param name="baseUrl">Base URL for the API.</param>
    /// <param name="timeout">Request timeout.</param>
    public FirecrawlIntegration(
        string apiKey,
        string baseUrl = "https://api.firecrawl.dev/v2",
        TimeSpan? timeout = null)
    {
        _baseUrl = baseUrl;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri(baseUrl),
            Timeout = timeout ?? TimeSpan.FromSeconds(60)
        };

        _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
    }

    /// <summary>
    /// Scrape a single URL with various options.
    /// </summary>
    /// <param name="parameters">Scraping parameters.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The scrape response.</returns>
    public async Task<FirecrawlScrapeResponse> ScrapeAsync(
        Dictionary<string, object?> parameters,
        CancellationToken cancellationToken = default)
    {
        // Clean and process parameters
        var cleanParams = CleanParameters(parameters);
        var processedParams = ProcessParameters(cleanParams);

        var httpRequest = new HttpRequestMessage(HttpMethod.Post, "/scrape")
        {
            Content = JsonContent.Create(processedParams)
        };

        var response = await _httpClient.SendAsync(httpRequest, cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            string errorMessage;

            try
            {
                var errorJson = JsonDocument.Parse(errorContent).RootElement;
                errorMessage = errorJson.TryGetProperty("error", out var err)
                    ? err.GetString() ?? response.ReasonPhrase ?? "Unknown error"
                    : response.ReasonPhrase ?? "Unknown error";
            }
            catch
            {
                errorMessage = response.ReasonPhrase ?? "Unknown error";
            }

            throw new HttpRequestException(
                $"Firecrawl API error: {(int)response.StatusCode} - {errorMessage}");
        }

        var result = await response.Content.ReadFromJsonAsync<FirecrawlScrapeResponse>(
            cancellationToken: cancellationToken);

        return result ?? new FirecrawlScrapeResponse { Success = false, Error = "Empty response" };
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

        // Parameter name mappings (snake_case to camelCase for API)
        var paramMappings = new Dictionary<string, string>
        {
            ["include_tags"] = "includeTags",
            ["exclude_tags"] = "excludeTags",
            ["only_main_content"] = "onlyMainContent",
            ["max_age"] = "maxAge",
            ["wait_for"] = "waitFor",
            ["mobile_device"] = "mobile",
            ["skip_tls_verification"] = "skipTlsVerification",
            ["remove_base64_images"] = "removeBase64Images",
            ["block_ads"] = "blockAds",
            ["store_in_cache"] = "storeInCache",
            ["zero_data_retention"] = "zeroDataRetention"
        };

        foreach (var (inputKey, apiKey) in paramMappings)
        {
            if (processed.TryGetValue(inputKey, out var value))
            {
                processed[apiKey] = value;
                processed.Remove(inputKey);
            }
        }

        // Convert comma-separated strings to arrays
        var arrayFields = new[] { "includeTags", "excludeTags", "formats" };
        foreach (var field in arrayFields)
        {
            if (processed.TryGetValue(field, out var value))
            {
                processed[field] = StringToArray(value);
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
