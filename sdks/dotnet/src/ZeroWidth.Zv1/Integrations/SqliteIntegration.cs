using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace ZeroWidth.Zv1.Integrations;

/// <summary>
/// Query result from SQLite.
/// </summary>
public record SqliteQueryResult
{
    /// <summary>Gets or sets whether the query succeeded.</summary>
    public bool Success { get; set; }

    /// <summary>Gets or sets the query data.</summary>
    public List<Dictionary<string, object?>>? Data { get; set; }

    /// <summary>Gets or sets the operation type.</summary>
    public string? Operation { get; set; }

    /// <summary>Gets or sets the row count.</summary>
    public int RowCount { get; set; }

    /// <summary>Gets or sets the last insert ID.</summary>
    public long? LastInsertId { get; set; }

    /// <summary>Gets or sets the changes count.</summary>
    public int? Changes { get; set; }
}

/// <summary>
/// Schema validation result.
/// </summary>
public record SchemaValidationResult
{
    /// <summary>Gets or sets whether the schema is valid.</summary>
    public bool Valid { get; set; }

    /// <summary>Gets or sets missing items.</summary>
    public Dictionary<string, object?>? Missing { get; set; }

    /// <summary>Gets or sets any error.</summary>
    public string? Error { get; set; }
}

/// <summary>
/// Knowledge base statistics.
/// </summary>
public record KnowledgeBaseStats
{
    /// <summary>Gets or sets document count.</summary>
    public int Documents { get; set; }

    /// <summary>Gets or sets chunk count.</summary>
    public int Chunks { get; set; }

    /// <summary>Gets or sets total size.</summary>
    public long TotalSize { get; set; }
}

/// <summary>
/// Semantic search result.
/// </summary>
public record SemanticSearchResult
{
    /// <summary>Gets or sets the chunk ID.</summary>
    public string? Id { get; set; }

    /// <summary>Gets or sets the document ID.</summary>
    public string? DocumentId { get; set; }

    /// <summary>Gets or sets the document name.</summary>
    public string? DocumentName { get; set; }

    /// <summary>Gets or sets the file type.</summary>
    public string? FileType { get; set; }

    /// <summary>Gets or sets the folder path.</summary>
    public string? FolderPath { get; set; }

    /// <summary>Gets or sets the chunk index.</summary>
    public int ChunkIndex { get; set; }

    /// <summary>Gets or sets the content.</summary>
    public string? Content { get; set; }

    /// <summary>Gets or sets the token count.</summary>
    public int? TokenCount { get; set; }

    /// <summary>Gets or sets the chunk type.</summary>
    public string? ChunkType { get; set; }

    /// <summary>Gets or sets the metadata.</summary>
    public Dictionary<string, object?>? Metadata { get; set; }

    /// <summary>Gets or sets the embedding model.</summary>
    public string? EmbeddingModel { get; set; }

    /// <summary>Gets or sets the embedding dimensions.</summary>
    public int? EmbeddingDimensions { get; set; }

    /// <summary>Gets or sets the similarity score.</summary>
    public double SimilarityScore { get; set; }

    /// <summary>Gets or sets the created at timestamp.</summary>
    public string? CreatedAt { get; set; }

    /// <summary>Gets or sets the match type (for text search fallback).</summary>
    public string? MatchType { get; set; }
}

/// <summary>
/// SQLite database integration with vector search support.
/// </summary>
public class SqliteIntegration : IAsyncDisposable
{
    private readonly string _dbPath;
    private SqliteConnection? _connection;
    private bool _isConnected;

    /// <summary>
    /// Initializes a new instance of the SqliteIntegration class.
    /// </summary>
    /// <param name="dbPath">Path to the SQLite database file.</param>
    public SqliteIntegration(string dbPath)
    {
        _dbPath = dbPath;
    }

    /// <summary>
    /// Initialize the database connection.
    /// </summary>
    public async Task ConnectAsync()
    {
        if (!File.Exists(_dbPath))
        {
            throw new FileNotFoundException($"Database file not found: {_dbPath}");
        }

        _connection = new SqliteConnection($"Data Source={_dbPath}");
        await _connection.OpenAsync();

        // Test connection
        using var cmd = _connection.CreateCommand();
        cmd.CommandText = "SELECT 1";
        await cmd.ExecuteScalarAsync();

        _isConnected = true;
    }

    /// <summary>
    /// Close the database connection.
    /// </summary>
    public async Task DisconnectAsync()
    {
        if (_connection != null && _isConnected)
        {
            await _connection.CloseAsync();
            _isConnected = false;
        }

        // Clean up temporary file if needed
        if (_dbPath.Contains(".temp") || _dbPath.Contains("knowledge_"))
        {
            try
            {
                if (File.Exists(_dbPath))
                {
                    File.Delete(_dbPath);
                }
            }
            catch
            {
                // Best effort cleanup
            }
        }
    }

    /// <summary>
    /// Execute a raw SQL query.
    /// </summary>
    /// <param name="query">SQL query to execute.</param>
    /// <param name="parameters">Query parameters.</param>
    /// <param name="operation">Type of operation.</param>
    /// <returns>Query result.</returns>
    public async Task<SqliteQueryResult> QueryAsync(
        string query,
        object?[]? parameters = null,
        string operation = "SELECT")
    {
        if (!_isConnected || _connection == null)
        {
            await ConnectAsync();
        }

        var allowedOperations = new[] { "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER" };
        var queryUpper = query.Trim().ToUpperInvariant();
        var isAllowed = allowedOperations.Any(op => queryUpper.StartsWith(op));

        if (!isAllowed)
        {
            throw new InvalidOperationException($"Operation not allowed: {queryUpper.Split(' ')[0]}");
        }

        using var cmd = _connection!.CreateCommand();
        cmd.CommandText = query;

        if (parameters != null)
        {
            for (var i = 0; i < parameters.Length; i++)
            {
                cmd.Parameters.AddWithValue($"@p{i}", parameters[i] ?? DBNull.Value);
            }
        }

        var result = new SqliteQueryResult
        {
            Success = true,
            Operation = operation.ToUpperInvariant()
        };

        if (operation.Equals("SELECT", StringComparison.OrdinalIgnoreCase))
        {
            var data = new List<Dictionary<string, object?>>();
            using var reader = await cmd.ExecuteReaderAsync();

            while (await reader.ReadAsync())
            {
                var row = new Dictionary<string, object?>();
                for (var i = 0; i < reader.FieldCount; i++)
                {
                    row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                }
                data.Add(row);
            }

            result.Data = data;
            result.RowCount = data.Count;
        }
        else
        {
            var changes = await cmd.ExecuteNonQueryAsync();
            result.Changes = changes;
            result.RowCount = changes;

            // For INSERT, get the last insert ID
            if (operation.Equals("INSERT", StringComparison.OrdinalIgnoreCase))
            {
                using var lastIdCmd = _connection.CreateCommand();
                lastIdCmd.CommandText = "SELECT last_insert_rowid()";
                result.LastInsertId = (long?)await lastIdCmd.ExecuteScalarAsync();
            }
        }

        return result;
    }

    /// <summary>
    /// Execute a SELECT query.
    /// </summary>
    public async Task<List<Dictionary<string, object?>>> SelectAsync(
        string query,
        object?[]? parameters = null)
    {
        var result = await QueryAsync(query, parameters, "SELECT");
        return result.Data ?? new List<Dictionary<string, object?>>();
    }

    /// <summary>
    /// Execute an INSERT query.
    /// </summary>
    public async Task<SqliteQueryResult> InsertAsync(
        string query,
        object?[]? parameters = null)
    {
        return await QueryAsync(query, parameters, "INSERT");
    }

    /// <summary>
    /// Execute an UPDATE query.
    /// </summary>
    public async Task<SqliteQueryResult> UpdateAsync(
        string query,
        object?[]? parameters = null)
    {
        return await QueryAsync(query, parameters, "UPDATE");
    }

    /// <summary>
    /// Execute a DELETE query.
    /// </summary>
    public async Task<SqliteQueryResult> DeleteAsync(
        string query,
        object?[]? parameters = null)
    {
        return await QueryAsync(query, parameters, "DELETE");
    }

    /// <summary>
    /// Get database schema information.
    /// </summary>
    public async Task<Dictionary<string, List<Dictionary<string, object?>>>> GetSchemaAsync()
    {
        var tables = await SelectAsync(@"
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name");

        var schema = new Dictionary<string, List<Dictionary<string, object?>>>();

        foreach (var table in tables)
        {
            var tableName = table["name"]?.ToString();
            if (tableName != null)
            {
                var columns = await SelectAsync($"PRAGMA table_info({tableName})");
                schema[tableName] = columns;
            }
        }

        return schema;
    }

    /// <summary>
    /// Check if the database has the expected knowledge base schema.
    /// </summary>
    public async Task<SchemaValidationResult> ValidateKnowledgeBaseSchemaAsync()
    {
        try
        {
            var schema = await GetSchemaAsync();

            var hasDocuments = schema.ContainsKey("documents");
            var hasChunks = schema.ContainsKey("chunks");

            if (!hasDocuments || !hasChunks)
            {
                return new SchemaValidationResult
                {
                    Valid = false,
                    Missing = new Dictionary<string, object?>
                    {
                        ["documents"] = !hasDocuments,
                        ["chunks"] = !hasChunks
                    }
                };
            }

            var documentsColumns = schema["documents"].Select(c => c["name"]?.ToString()).ToHashSet();
            var requiredDocColumns = new[] { "id", "display_name", "file_type", "file_size", "created_by", "created_at", "updated_at" };
            var missingDocColumns = requiredDocColumns.Where(c => !documentsColumns.Contains(c)).ToList();

            var chunksColumns = schema["chunks"].Select(c => c["name"]?.ToString()).ToHashSet();
            var requiredChunkColumns = new[] { "id", "document_id", "chunk_index", "content", "created_at", "updated_at" };
            var missingChunkColumns = requiredChunkColumns.Where(c => !chunksColumns.Contains(c)).ToList();

            return new SchemaValidationResult
            {
                Valid = missingDocColumns.Count == 0 && missingChunkColumns.Count == 0,
                Missing = new Dictionary<string, object?>
                {
                    ["documents"] = missingDocColumns,
                    ["chunks"] = missingChunkColumns
                }
            };
        }
        catch (Exception ex)
        {
            return new SchemaValidationResult
            {
                Valid = false,
                Error = ex.Message
            };
        }
    }

    /// <summary>
    /// Get basic statistics about the knowledge base.
    /// </summary>
    public async Task<KnowledgeBaseStats> GetStatsAsync()
    {
        var docCount = await SelectAsync("SELECT COUNT(*) as count FROM documents");
        var chunkCount = await SelectAsync("SELECT COUNT(*) as count FROM chunks");
        var totalSize = await SelectAsync("SELECT SUM(file_size) as total_size FROM documents");

        return new KnowledgeBaseStats
        {
            Documents = Convert.ToInt32(docCount.FirstOrDefault()?["count"] ?? 0),
            Chunks = Convert.ToInt32(chunkCount.FirstOrDefault()?["count"] ?? 0),
            TotalSize = Convert.ToInt64(totalSize.FirstOrDefault()?["total_size"] ?? 0L)
        };
    }

    /// <summary>
    /// Get the embedding model used by this knowledge base.
    /// </summary>
    public async Task<string> GetEmbeddingModelAsync()
    {
        try
        {
            var result = await SelectAsync(
                "SELECT embedding_model FROM chunks WHERE embedding_model IS NOT NULL ORDER BY created_at DESC LIMIT 1");

            if (result.Count > 0 && result[0]["embedding_model"] is string model)
            {
                return model;
            }
        }
        catch
        {
            // Fall through to default
        }

        return "text-embedding-3-small";
    }

    /// <summary>
    /// Perform semantic search (falls back to text search if vector search unavailable).
    /// </summary>
    public async Task<List<SemanticSearchResult>> SemanticSearchAsync(
        string query,
        int limit = 10,
        double similarityThreshold = 0.7,
        string? documentId = null,
        string? embeddingModel = null,
        List<double>? queryEmbedding = null)
    {
        if (!_isConnected)
        {
            await ConnectAsync();
        }

        // For now, fall back to text search since sqlite-vec extension
        // requires native library loading which is complex in .NET
        return await FallbackTextSearchAsync(query, limit, documentId);
    }

    private async Task<List<SemanticSearchResult>> FallbackTextSearchAsync(
        string query,
        int limit = 10,
        string? documentId = null)
    {
        var sql = @"
            SELECT
                c.id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.token_count,
                c.chunk_type,
                c.metadata,
                d.display_name as document_name,
                d.file_type,
                d.folder_path,
                c.created_at
            FROM chunks c
            LEFT JOIN documents d ON c.document_id = d.id
            WHERE c.content LIKE @p0";

        var parameters = new List<object?> { $"%{query}%" };

        if (!string.IsNullOrEmpty(documentId))
        {
            sql += " AND c.document_id = @p1";
            parameters.Add(documentId);
        }

        sql += " ORDER BY c.created_at DESC LIMIT @p" + parameters.Count;
        parameters.Add(limit);

        var results = await SelectAsync(sql, parameters.ToArray());

        return results.Select((row, index) => new SemanticSearchResult
        {
            Id = row["id"]?.ToString(),
            DocumentId = row["document_id"]?.ToString(),
            DocumentName = row["document_name"]?.ToString(),
            FileType = row["file_type"]?.ToString(),
            FolderPath = row["folder_path"]?.ToString(),
            ChunkIndex = Convert.ToInt32(row["chunk_index"] ?? 0),
            Content = row["content"]?.ToString(),
            TokenCount = row["token_count"] != null ? Convert.ToInt32(row["token_count"]) : null,
            ChunkType = row["chunk_type"]?.ToString(),
            Metadata = ParseMetadata(row["metadata"]),
            CreatedAt = row["created_at"]?.ToString(),
            SimilarityScore = 1.0 - (index * 0.1), // Mock decreasing similarity
            MatchType = "text_search"
        }).ToList();
    }

    private static Dictionary<string, object?>? ParseMetadata(object? metadata)
    {
        if (metadata == null) return null;

        var metadataStr = metadata.ToString();
        if (string.IsNullOrEmpty(metadataStr)) return null;

        try
        {
            var doc = JsonDocument.Parse(metadataStr);
            var result = new Dictionary<string, object?>();

            foreach (var prop in doc.RootElement.EnumerateObject())
            {
                result[prop.Name] = prop.Value.ValueKind switch
                {
                    JsonValueKind.String => prop.Value.GetString(),
                    JsonValueKind.Number => prop.Value.GetDouble(),
                    JsonValueKind.True => true,
                    JsonValueKind.False => false,
                    JsonValueKind.Null => null,
                    _ => prop.Value.GetRawText()
                };
            }

            return result;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Disposes of the database connection.
    /// </summary>
    public async ValueTask DisposeAsync()
    {
        await DisconnectAsync();
        _connection?.Dispose();
    }
}
