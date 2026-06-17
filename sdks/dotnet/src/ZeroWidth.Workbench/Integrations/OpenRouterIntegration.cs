using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ZeroWidth.Workbench.Integrations;

/// <summary>
/// Token usage statistics.
/// </summary>
public record UsageStats
{
    /// <summary>Gets or sets the prompt tokens.</summary>
    [JsonPropertyName("prompt_tokens")]
    public int PromptTokens { get; set; }

    /// <summary>Gets or sets the completion tokens.</summary>
    [JsonPropertyName("completion_tokens")]
    public int CompletionTokens { get; set; }

    /// <summary>Gets or sets the total tokens.</summary>
    [JsonPropertyName("total_tokens")]
    public int TotalTokens { get; set; }
}

/// <summary>
/// Cost breakdown for a request.
/// </summary>
public record CostBreakdown
{
    /// <summary>Gets the total cost.</summary>
    public double TotalCost { get; init; }

    /// <summary>Gets the itemized costs.</summary>
    public List<CostItem> ItemizedCosts { get; init; } = new();
}

/// <summary>
/// Individual cost item.
/// </summary>
public record CostItem
{
    /// <summary>Gets the label.</summary>
    public required string Label { get; init; }

    /// <summary>Gets the cost.</summary>
    public double Cost { get; init; }

    /// <summary>Gets the token count.</summary>
    public int Tokens { get; init; }
}

/// <summary>
/// Chat completion response.
/// </summary>
public record ChatCompletionResponse
{
    /// <summary>Gets or sets the content.</summary>
    public string Content { get; set; } = "";

    /// <summary>Gets or sets the role.</summary>
    public string Role { get; set; } = "assistant";

    /// <summary>Gets or sets the finish reason.</summary>
    public string? FinishReason { get; set; }

    /// <summary>Gets or sets tool calls.</summary>
    public List<ToolCall>? ToolCalls { get; set; }

    /// <summary>Gets or sets the model used.</summary>
    public string? Model { get; set; }

    /// <summary>Gets or sets usage statistics.</summary>
    public UsageStats Usage { get; set; } = new();

    /// <summary>Gets or sets reasoning content.</summary>
    public string? Reasoning { get; set; }

    /// <summary>Gets or sets the total cost.</summary>
    public double? CostTotal { get; set; }

    /// <summary>Gets or sets itemized costs.</summary>
    public List<CostItem>? CostItemized { get; set; }
}

/// <summary>
/// Tool call information.
/// </summary>
public record ToolCall
{
    /// <summary>Gets or sets the tool call ID.</summary>
    public required string Id { get; set; }

    /// <summary>Gets or sets the index.</summary>
    public int Index { get; set; }

    /// <summary>Gets or sets the type.</summary>
    public string Type { get; set; } = "function";

    /// <summary>Gets or sets the function details.</summary>
    public required ToolCallFunction Function { get; set; }
}

/// <summary>
/// Tool call function details.
/// </summary>
public record ToolCallFunction
{
    /// <summary>Gets or sets the function name.</summary>
    public required string Name { get; set; }

    /// <summary>Gets or sets the arguments.</summary>
    public object? Arguments { get; set; }
}

/// <summary>
/// Integration with OpenRouter's AI model API.
/// </summary>
public class OpenRouterIntegration : IAsyncDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;

    /// <summary>
    /// Initializes a new instance of the OpenRouterIntegration class.
    /// </summary>
    /// <param name="apiKey">OpenRouter API key.</param>
    /// <param name="baseUrl">Base URL for the API.</param>
    /// <param name="referer">HTTP Referer header value.</param>
    /// <param name="title">X-Title header value.</param>
    public OpenRouterIntegration(
        string apiKey,
        string baseUrl = "https://openrouter.ai/api/v1",
        string referer = "https://workbench.zerowidth.ai",
        string title = "Workbench by ZeroWidth")
    {
        _baseUrl = baseUrl;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri(baseUrl),
            Timeout = TimeSpan.FromMinutes(5)
        };

        _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
        _httpClient.DefaultRequestHeaders.Add("HTTP-Referer", referer);
        _httpClient.DefaultRequestHeaders.Add("X-Title", title);
    }

    /// <summary>
    /// Makes a chat completion request to OpenRouter.
    /// </summary>
    /// <param name="request">The chat completion request.</param>
    /// <param name="nodeConfig">Node configuration for cost calculation.</param>
    /// <param name="onUpdate">Callback for streaming updates.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The chat completion response.</returns>
    public async Task<ChatCompletionResponse> ChatCompletionAsync(
        ChatCompletionRequest request,
        JsonElement? nodeConfig = null,
        Action<StreamEvent>? onUpdate = null,
        CancellationToken cancellationToken = default)
    {
        var payload = BuildPayload(request);

        // Enable streaming
        payload["stream"] = true;

        var httpRequest = new HttpRequestMessage(HttpMethod.Post, "/chat/completions")
        {
            Content = JsonContent.Create(payload)
        };

        var response = await _httpClient.SendAsync(
            httpRequest,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);

        response.EnsureSuccessStatusCode();

        return await ProcessStreamResponseAsync(
            response,
            nodeConfig,
            onUpdate,
            request.Model,
            cancellationToken);
    }

    private Dictionary<string, object?> BuildPayload(ChatCompletionRequest request)
    {
        var payload = new Dictionary<string, object?>
        {
            ["model"] = request.Model,
            ["provider"] = new Dictionary<string, object>
            {
                ["data_collection"] = "deny",
                ["require_parameters"] = true
            }
        };

        // Add messages
        if (request.Messages != null)
        {
            payload["messages"] = CleanMessages(request.Messages);
        }
        else if (request.Prompt != null)
        {
            payload["prompt"] = request.Prompt;
        }

        // Handle tools
        if (request.Tools != null && request.Tools.Count > 0)
        {
            payload["tools"] = request.Tools.Select(tool => new Dictionary<string, object?>
            {
                ["type"] = "function",
                ["function"] = new Dictionary<string, object?>
                {
                    ["name"] = tool.Name,
                    ["description"] = tool.Description,
                    ["parameters"] = tool.Parameters
                }
            }).ToList();
        }

        // Handle reasoning parameter
        if (request.Reasoning.HasValue)
        {
            payload["reasoning"] = new Dictionary<string, object>
            {
                ["enabled"] = request.Reasoning.Value
            };
        }

        // Add other parameters
        if (request.Temperature.HasValue)
            payload["temperature"] = request.Temperature.Value;
        if (request.MaxTokens.HasValue)
            payload["max_tokens"] = request.MaxTokens.Value;
        if (request.TopP.HasValue)
            payload["top_p"] = request.TopP.Value;
        if (request.FrequencyPenalty.HasValue)
            payload["frequency_penalty"] = request.FrequencyPenalty.Value;
        if (request.PresencePenalty.HasValue)
            payload["presence_penalty"] = request.PresencePenalty.Value;

        return payload;
    }

    private static List<Dictionary<string, object?>> CleanMessages(
        List<Dictionary<string, object?>> messages)
    {
        return messages.Select(msg =>
        {
            var clean = new Dictionary<string, object?>(msg);

            // Remove internal fields
            clean.Remove("id");
            clean.Remove("participant_id");
            clean.Remove("timestamp");

            // Remove empty tool_calls
            if (clean.TryGetValue("tool_calls", out var tc) &&
                tc is ICollection<object> collection &&
                collection.Count == 0)
            {
                clean.Remove("tool_calls");
            }

            return clean;
        }).ToList();
    }

    private async Task<ChatCompletionResponse> ProcessStreamResponseAsync(
        HttpResponseMessage response,
        JsonElement? nodeConfig,
        Action<StreamEvent>? onUpdate,
        string model,
        CancellationToken cancellationToken)
    {
        var result = new ChatCompletionResponse { Model = model };
        var toolCalls = new List<ToolCall>();
        var count = 0;

        using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var reader = new StreamReader(stream);

        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync(cancellationToken);
            if (string.IsNullOrEmpty(line) || !line.StartsWith("data: "))
                continue;

            var data = line.Substring(6);
            if (data == "[DONE]")
                break;

            try
            {
                var chunk = JsonSerializer.Deserialize<JsonElement>(data);
                ProcessChunk(chunk, result, toolCalls, onUpdate, ref count);
            }
            catch (JsonException)
            {
                // Skip invalid JSON
            }
        }

        result.ToolCalls = toolCalls.Count > 0 ? toolCalls : null;

        // Calculate costs
        if (nodeConfig.HasValue)
        {
            var costs = CalculateCosts(result.Usage, nodeConfig.Value);
            result.CostTotal = costs.TotalCost;
            result.CostItemized = costs.ItemizedCosts;
        }

        return result;
    }

    private void ProcessChunk(
        JsonElement chunk,
        ChatCompletionResponse result,
        List<ToolCall> toolCalls,
        Action<StreamEvent>? onUpdate,
        ref int count)
    {
        if (!chunk.TryGetProperty("choices", out var choices) || choices.GetArrayLength() == 0)
            return;

        var choice = choices[0];
        var eventData = new Dictionary<string, object?>();

        if (choice.TryGetProperty("delta", out var delta))
        {
            if (delta.TryGetProperty("content", out var content) &&
                content.ValueKind == JsonValueKind.String)
            {
                var contentStr = content.GetString();
                result.Content += contentStr;
                eventData["content"] = contentStr;
            }

            if (delta.TryGetProperty("reasoning", out var reasoning) &&
                reasoning.ValueKind == JsonValueKind.String)
            {
                result.Reasoning = (result.Reasoning ?? "") + reasoning.GetString();
                eventData["reasoning"] = reasoning.GetString();
            }

            if (delta.TryGetProperty("role", out var role))
            {
                result.Role = role.GetString() ?? "assistant";
                eventData["role"] = result.Role;
            }

            if (delta.TryGetProperty("tool_calls", out var deltaTcs))
            {
                ProcessToolCalls(deltaTcs, toolCalls);
                eventData["tool_calls"] = deltaTcs;
            }
        }

        if (choice.TryGetProperty("finish_reason", out var finishReason) &&
            finishReason.ValueKind == JsonValueKind.String)
        {
            result.FinishReason = finishReason.GetString();
            eventData["finish_reason"] = result.FinishReason;
        }

        // Update usage
        if (chunk.TryGetProperty("usage", out var usage))
        {
            if (usage.TryGetProperty("prompt_tokens", out var pt))
                result.Usage.PromptTokens += pt.GetInt32();
            if (usage.TryGetProperty("completion_tokens", out var ct))
                result.Usage.CompletionTokens += ct.GetInt32();
            if (usage.TryGetProperty("total_tokens", out var tt))
                result.Usage.TotalTokens += tt.GetInt32();
        }

        // Invoke callback
        onUpdate?.Invoke(new StreamEvent
        {
            Count = count++,
            Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            Data = eventData
        });
    }

    private static void ProcessToolCalls(JsonElement deltaTcs, List<ToolCall> toolCalls)
    {
        foreach (var tc in deltaTcs.EnumerateArray())
        {
            if (tc.TryGetProperty("id", out var id) && id.ValueKind == JsonValueKind.String)
            {
                // New tool call
                var name = tc.TryGetProperty("function", out var fn) &&
                           fn.TryGetProperty("name", out var n)
                    ? n.GetString() ?? ""
                    : "";

                var args = fn.TryGetProperty("arguments", out var a)
                    ? a.GetString() ?? ""
                    : "";

                toolCalls.Add(new ToolCall
                {
                    Id = id.GetString()!,
                    Index = tc.TryGetProperty("index", out var idx) ? idx.GetInt32() : 0,
                    Type = tc.TryGetProperty("type", out var t) ? t.GetString() ?? "function" : "function",
                    Function = new ToolCallFunction
                    {
                        Name = name,
                        Arguments = args
                    }
                });
            }
            else if (toolCalls.Count > 0)
            {
                // Append to most recent tool call's arguments
                if (tc.TryGetProperty("function", out var fn) &&
                    fn.TryGetProperty("arguments", out var args))
                {
                    var lastTc = toolCalls[^1];
                    var currentArgs = lastTc.Function.Arguments?.ToString() ?? "";
                    lastTc.Function.Arguments = currentArgs + args.GetString();
                }
            }
        }
    }

    /// <summary>
    /// Calculates costs based on usage and pricing information.
    /// </summary>
    public static CostBreakdown CalculateCosts(UsageStats usage, JsonElement nodeConfig)
    {
        if (!nodeConfig.TryGetProperty("pricing", out var pricing) ||
            !pricing.TryGetProperty("items", out var items))
        {
            return new CostBreakdown();
        }

        double inputCostPerMillion = 0;
        double outputCostPerMillion = 0;

        foreach (var item in items.EnumerateArray())
        {
            var key = item.TryGetProperty("key", out var k) ? k.GetString() : null;
            var cost = item.TryGetProperty("cost", out var c) ? c.GetDouble() : 0;

            if (key == "input_cost_per_million")
                inputCostPerMillion = cost;
            else if (key == "output_cost_per_million")
                outputCostPerMillion = cost;
        }

        var inputCost = usage.PromptTokens * (inputCostPerMillion / 1_000_000);
        var outputCost = usage.CompletionTokens * (outputCostPerMillion / 1_000_000);
        var totalCost = Math.Round(inputCost + outputCost, 8);

        return new CostBreakdown
        {
            TotalCost = totalCost,
            ItemizedCosts = new List<CostItem>
            {
                new() { Label = "Input Tokens", Cost = Math.Round(inputCost, 8), Tokens = usage.PromptTokens },
                new() { Label = "Output Tokens", Cost = Math.Round(outputCost, 8), Tokens = usage.CompletionTokens }
            }
        };
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

/// <summary>
/// Chat completion request.
/// </summary>
public record ChatCompletionRequest
{
    /// <summary>Gets or sets the model identifier.</summary>
    public required string Model { get; init; }

    /// <summary>Gets or sets the messages.</summary>
    public List<Dictionary<string, object?>>? Messages { get; init; }

    /// <summary>Gets or sets the prompt (alternative to messages).</summary>
    public string? Prompt { get; init; }

    /// <summary>Gets or sets the tools.</summary>
    public List<ToolDefinition>? Tools { get; init; }

    /// <summary>Gets or sets whether to enable reasoning.</summary>
    public bool? Reasoning { get; init; }

    /// <summary>Gets or sets the temperature.</summary>
    public double? Temperature { get; init; }

    /// <summary>Gets or sets the max tokens.</summary>
    public int? MaxTokens { get; init; }

    /// <summary>Gets or sets the top P value.</summary>
    public double? TopP { get; init; }

    /// <summary>Gets or sets the frequency penalty.</summary>
    public double? FrequencyPenalty { get; init; }

    /// <summary>Gets or sets the presence penalty.</summary>
    public double? PresencePenalty { get; init; }
}

/// <summary>
/// Tool definition.
/// </summary>
public record ToolDefinition
{
    /// <summary>Gets or sets the tool name.</summary>
    public required string Name { get; init; }

    /// <summary>Gets or sets the tool description.</summary>
    public string? Description { get; init; }

    /// <summary>Gets or sets the tool parameters schema.</summary>
    public object? Parameters { get; init; }
}

/// <summary>
/// Streaming event.
/// </summary>
public record StreamEvent
{
    /// <summary>Gets the event count.</summary>
    public int Count { get; init; }

    /// <summary>Gets the timestamp.</summary>
    public long Timestamp { get; init; }

    /// <summary>Gets the event data.</summary>
    public Dictionary<string, object?>? Data { get; init; }
}
