using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ZeroWidth.Workbench.Integrations;

/// <summary>
/// Embedding response from OpenAI.
/// </summary>
public record EmbeddingResponse
{
    /// <summary>Gets or sets the embedding data.</summary>
    public List<EmbeddingData> Data { get; set; } = new();

    /// <summary>Gets or sets the model used.</summary>
    public string? Model { get; set; }

    /// <summary>Gets or sets usage statistics.</summary>
    public EmbeddingUsage? Usage { get; set; }
}

/// <summary>
/// Individual embedding data.
/// </summary>
public record EmbeddingData
{
    /// <summary>Gets or sets the embedding vector.</summary>
    [JsonPropertyName("embedding")]
    public List<double> Embedding { get; set; } = new();

    /// <summary>Gets or sets the index.</summary>
    [JsonPropertyName("index")]
    public int Index { get; set; }
}

/// <summary>
/// Embedding usage statistics.
/// </summary>
public record EmbeddingUsage
{
    /// <summary>Gets or sets prompt tokens.</summary>
    [JsonPropertyName("prompt_tokens")]
    public int PromptTokens { get; set; }

    /// <summary>Gets or sets total tokens.</summary>
    [JsonPropertyName("total_tokens")]
    public int TotalTokens { get; set; }
}

/// <summary>
/// Content moderation response.
/// </summary>
public record ModerationResponse
{
    /// <summary>Gets or sets whether content was flagged.</summary>
    public bool Flagged { get; set; }

    /// <summary>Gets or sets whether sexual content was detected.</summary>
    public bool Sexual { get; set; }

    /// <summary>Gets or sets the sexual content score.</summary>
    public double SexualScore { get; set; }

    /// <summary>Gets or sets whether sexual content involving minors was detected.</summary>
    public bool SexualMinors { get; set; }

    /// <summary>Gets or sets the sexual minors score.</summary>
    public double SexualMinorsScore { get; set; }

    /// <summary>Gets or sets whether harassment was detected.</summary>
    public bool Harassment { get; set; }

    /// <summary>Gets or sets the harassment score.</summary>
    public double HarassmentScore { get; set; }

    /// <summary>Gets or sets whether threatening harassment was detected.</summary>
    public bool HarassmentThreatening { get; set; }

    /// <summary>Gets or sets the threatening harassment score.</summary>
    public double HarassmentThreateningScore { get; set; }

    /// <summary>Gets or sets whether hate content was detected.</summary>
    public bool Hate { get; set; }

    /// <summary>Gets or sets the hate score.</summary>
    public double HateScore { get; set; }

    /// <summary>Gets or sets whether threatening hate content was detected.</summary>
    public bool HateThreatening { get; set; }

    /// <summary>Gets or sets the threatening hate score.</summary>
    public double HateThreateningScore { get; set; }

    /// <summary>Gets or sets whether illicit content was detected.</summary>
    public bool Illicit { get; set; }

    /// <summary>Gets or sets the illicit score.</summary>
    public double IllicitScore { get; set; }

    /// <summary>Gets or sets whether violent illicit content was detected.</summary>
    public bool IllicitViolent { get; set; }

    /// <summary>Gets or sets the violent illicit score.</summary>
    public double IllicitViolentScore { get; set; }

    /// <summary>Gets or sets whether self-harm content was detected.</summary>
    public bool SelfHarm { get; set; }

    /// <summary>Gets or sets the self-harm score.</summary>
    public double SelfHarmScore { get; set; }

    /// <summary>Gets or sets whether self-harm intent was detected.</summary>
    public bool SelfHarmIntent { get; set; }

    /// <summary>Gets or sets the self-harm intent score.</summary>
    public double SelfHarmIntentScore { get; set; }

    /// <summary>Gets or sets whether self-harm instructions were detected.</summary>
    public bool SelfHarmInstructions { get; set; }

    /// <summary>Gets or sets the self-harm instructions score.</summary>
    public double SelfHarmInstructionsScore { get; set; }

    /// <summary>Gets or sets whether violence was detected.</summary>
    public bool Violence { get; set; }

    /// <summary>Gets or sets the violence score.</summary>
    public double ViolenceScore { get; set; }

    /// <summary>Gets or sets whether graphic violence was detected.</summary>
    public bool ViolenceGraphic { get; set; }

    /// <summary>Gets or sets the graphic violence score.</summary>
    public double ViolenceGraphicScore { get; set; }
}

/// <summary>
/// Integration with OpenAI API for embeddings and moderation.
/// </summary>
public class OpenAIIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;

    /// <summary>
    /// Initializes a new instance of the OpenAIIntegration class.
    /// </summary>
    /// <param name="apiKey">OpenAI API key.</param>
    /// <param name="timeout">Request timeout.</param>
    public OpenAIIntegration(
        string apiKey,
        TimeSpan? timeout = null)
    {
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri("https://api.openai.com/v1/"),
            Timeout = timeout ?? TimeSpan.FromSeconds(30)
        };

        _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
    }

    /// <summary>
    /// Create embeddings for text using OpenAI's embedding models.
    /// </summary>
    /// <param name="input">Text or array of texts to embed.</param>
    /// <param name="model">Embedding model to use.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Embedding response.</returns>
    public async Task<EmbeddingResponse> CreateEmbeddingAsync(
        object input,
        string model = "text-embedding-3-small",
        CancellationToken cancellationToken = default)
    {
        var payload = new Dictionary<string, object>
        {
            ["model"] = model,
            ["input"] = input
        };

        var httpRequest = new HttpRequestMessage(HttpMethod.Post, "embeddings")
        {
            Content = JsonContent.Create(payload)
        };

        var response = await _httpClient.SendAsync(httpRequest, cancellationToken);

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
                $"OpenAI Embeddings API error: {(int)response.StatusCode} - {errorMessage}");
        }

        var content = await response.Content.ReadAsStringAsync(cancellationToken);
        var jsonDoc = JsonDocument.Parse(content);
        var root = jsonDoc.RootElement;

        var result = new EmbeddingResponse();

        if (root.TryGetProperty("data", out var data))
        {
            foreach (var item in data.EnumerateArray())
            {
                var embeddingData = new EmbeddingData { Index = item.GetProperty("index").GetInt32() };

                if (item.TryGetProperty("embedding", out var embedding))
                {
                    embeddingData.Embedding = embedding.EnumerateArray()
                        .Select(e => e.GetDouble())
                        .ToList();
                }

                result.Data.Add(embeddingData);
            }
        }

        if (root.TryGetProperty("model", out var modelProp))
            result.Model = modelProp.GetString();

        if (root.TryGetProperty("usage", out var usage))
        {
            result.Usage = new EmbeddingUsage
            {
                PromptTokens = usage.TryGetProperty("prompt_tokens", out var pt) ? pt.GetInt32() : 0,
                TotalTokens = usage.TryGetProperty("total_tokens", out var tt) ? tt.GetInt32() : 0
            };
        }

        return result;
    }

    /// <summary>
    /// Moderate content using OpenAI's moderation API.
    /// </summary>
    /// <param name="input">Content to moderate.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Moderation results.</returns>
    public async Task<ModerationResponse> ModerateContentAsync(
        object input,
        CancellationToken cancellationToken = default)
    {
        // Extract content from message object if needed
        object moderationInput = input;

        if (input is Dictionary<string, object?> dict && dict.TryGetValue("content", out var content))
        {
            moderationInput = content ?? input;
        }
        else if (input is JsonElement element && element.ValueKind == JsonValueKind.Object)
        {
            if (element.TryGetProperty("content", out var contentEl))
            {
                moderationInput = contentEl.ValueKind == JsonValueKind.String
                    ? contentEl.GetString()!
                    : contentEl;
            }
        }

        var payload = new Dictionary<string, object>
        {
            ["model"] = "omni-moderation-latest",
            ["input"] = moderationInput
        };

        var httpRequest = new HttpRequestMessage(HttpMethod.Post, "moderations")
        {
            Content = JsonContent.Create(payload)
        };

        var response = await _httpClient.SendAsync(httpRequest, cancellationToken);

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
                $"OpenAI Moderation API error: {(int)response.StatusCode} - {errorMessage}");
        }

        var resultContent = await response.Content.ReadAsStringAsync(cancellationToken);
        var jsonDoc = JsonDocument.Parse(resultContent);
        var root = jsonDoc.RootElement;

        var moderationResponse = new ModerationResponse();

        if (root.TryGetProperty("results", out var results) && results.GetArrayLength() > 0)
        {
            var result = results[0];

            moderationResponse.Flagged = result.TryGetProperty("flagged", out var flagged) && flagged.GetBoolean();

            if (result.TryGetProperty("categories", out var categories))
            {
                moderationResponse.Sexual = GetBool(categories, "sexual");
                moderationResponse.SexualMinors = GetBool(categories, "sexual/minors");
                moderationResponse.Harassment = GetBool(categories, "harassment");
                moderationResponse.HarassmentThreatening = GetBool(categories, "harassment/threatening");
                moderationResponse.Hate = GetBool(categories, "hate");
                moderationResponse.HateThreatening = GetBool(categories, "hate/threatening");
                moderationResponse.Illicit = GetBool(categories, "illicit");
                moderationResponse.IllicitViolent = GetBool(categories, "illicit/violent");
                moderationResponse.SelfHarm = GetBool(categories, "self-harm");
                moderationResponse.SelfHarmIntent = GetBool(categories, "self-harm/intent");
                moderationResponse.SelfHarmInstructions = GetBool(categories, "self-harm/instructions");
                moderationResponse.Violence = GetBool(categories, "violence");
                moderationResponse.ViolenceGraphic = GetBool(categories, "violence/graphic");
            }

            if (result.TryGetProperty("category_scores", out var scores))
            {
                moderationResponse.SexualScore = GetDouble(scores, "sexual");
                moderationResponse.SexualMinorsScore = GetDouble(scores, "sexual/minors");
                moderationResponse.HarassmentScore = GetDouble(scores, "harassment");
                moderationResponse.HarassmentThreateningScore = GetDouble(scores, "harassment/threatening");
                moderationResponse.HateScore = GetDouble(scores, "hate");
                moderationResponse.HateThreateningScore = GetDouble(scores, "hate/threatening");
                moderationResponse.IllicitScore = GetDouble(scores, "illicit");
                moderationResponse.IllicitViolentScore = GetDouble(scores, "illicit/violent");
                moderationResponse.SelfHarmScore = GetDouble(scores, "self-harm");
                moderationResponse.SelfHarmIntentScore = GetDouble(scores, "self-harm/intent");
                moderationResponse.SelfHarmInstructionsScore = GetDouble(scores, "self-harm/instructions");
                moderationResponse.ViolenceScore = GetDouble(scores, "violence");
                moderationResponse.ViolenceGraphicScore = GetDouble(scores, "violence/graphic");
            }
        }

        return moderationResponse;
    }

    private static bool GetBool(JsonElement element, string property)
    {
        return element.TryGetProperty(property, out var prop) && prop.GetBoolean();
    }

    private static double GetDouble(JsonElement element, string property)
    {
        return element.TryGetProperty(property, out var prop) ? prop.GetDouble() : 0;
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
