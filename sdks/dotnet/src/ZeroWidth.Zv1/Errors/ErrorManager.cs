using Microsoft.Extensions.Logging;

namespace ZeroWidth.Zv1.Errors;

/// <summary>
/// Details about an error event.
/// </summary>
public record ErrorEvent
{
    /// <summary>Gets the error that occurred.</summary>
    public required Zv1Exception Error { get; init; }

    /// <summary>Gets the timestamp when the error occurred.</summary>
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;

    /// <summary>Gets whether the error was handled.</summary>
    public bool Handled { get; set; }
}

/// <summary>
/// Manages error handling and callbacks for the zv1 engine.
/// </summary>
public class ErrorManager
{
    private readonly ILogger? _logger;
    private readonly List<ErrorEvent> _errors = new();
    private readonly object _lock = new();

    /// <summary>
    /// Event raised when an error occurs.
    /// </summary>
    public event EventHandler<ErrorEvent>? OnError;

    /// <summary>
    /// Gets all recorded errors.
    /// </summary>
    public IReadOnlyList<ErrorEvent> Errors
    {
        get
        {
            lock (_lock)
            {
                return _errors.ToList().AsReadOnly();
            }
        }
    }

    /// <summary>
    /// Gets errors filtered by severity.
    /// </summary>
    public IReadOnlyList<ErrorEvent> GetErrorsBySeverity(ErrorSeverity severity)
    {
        lock (_lock)
        {
            return _errors.Where(e => e.Error.Severity == severity).ToList().AsReadOnly();
        }
    }

    /// <summary>
    /// Gets errors filtered by type.
    /// </summary>
    public IReadOnlyList<ErrorEvent> GetErrorsByType(ErrorType errorType)
    {
        lock (_lock)
        {
            return _errors.Where(e => e.Error.ErrorType == errorType).ToList().AsReadOnly();
        }
    }

    /// <summary>
    /// Gets errors for a specific node.
    /// </summary>
    public IReadOnlyList<ErrorEvent> GetErrorsByNode(string nodeId)
    {
        lock (_lock)
        {
            return _errors.Where(e => e.Error.NodeId == nodeId).ToList().AsReadOnly();
        }
    }

    /// <summary>
    /// Gets whether there are any critical errors.
    /// </summary>
    public bool HasCriticalErrors
    {
        get
        {
            lock (_lock)
            {
                return _errors.Any(e => e.Error.Severity == ErrorSeverity.Critical);
            }
        }
    }

    /// <summary>
    /// Initializes a new instance of the ErrorManager class.
    /// </summary>
    /// <param name="logger">Optional logger for error logging.</param>
    public ErrorManager(ILogger? logger = null)
    {
        _logger = logger;
    }

    /// <summary>
    /// Records an error and invokes error handlers.
    /// </summary>
    /// <param name="error">The error to record.</param>
    /// <returns>The recorded error event.</returns>
    public ErrorEvent RecordError(Zv1Exception error)
    {
        var errorEvent = new ErrorEvent { Error = error };

        lock (_lock)
        {
            _errors.Add(errorEvent);
        }

        // Log the error
        LogError(error);

        // Invoke error handlers
        try
        {
            OnError?.Invoke(this, errorEvent);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Error handler threw an exception");
        }

        return errorEvent;
    }

    /// <summary>
    /// Records an error from an exception.
    /// </summary>
    /// <param name="exception">The exception to record.</param>
    /// <param name="nodeId">Optional node ID where the error occurred.</param>
    /// <param name="nodeType">Optional node type where the error occurred.</param>
    /// <returns>The recorded error event.</returns>
    public ErrorEvent RecordError(Exception exception, string? nodeId = null, string? nodeType = null)
    {
        Zv1Exception zv1Error = exception switch
        {
            Zv1Exception zv1Ex => zv1Ex,
            OperationCanceledException => new TimeoutException(
                exception.Message,
                0,
                nodeId,
                nodeType,
                innerException: exception),
            _ => new NodeException(
                exception.Message,
                nodeId,
                nodeType,
                innerException: exception)
        };

        return RecordError(zv1Error);
    }

    /// <summary>
    /// Clears all recorded errors.
    /// </summary>
    public void Clear()
    {
        lock (_lock)
        {
            _errors.Clear();
        }
    }

    /// <summary>
    /// Creates a summary of all errors.
    /// </summary>
    public ErrorSummary GetSummary()
    {
        lock (_lock)
        {
            return new ErrorSummary
            {
                TotalErrors = _errors.Count,
                BySeverity = _errors
                    .GroupBy(e => e.Error.Severity)
                    .ToDictionary(g => g.Key, g => g.Count()),
                ByType = _errors
                    .GroupBy(e => e.Error.ErrorType)
                    .ToDictionary(g => g.Key, g => g.Count()),
                ByNode = _errors
                    .Where(e => e.Error.NodeId != null)
                    .GroupBy(e => e.Error.NodeId!)
                    .ToDictionary(g => g.Key, g => g.Count())
            };
        }
    }

    private void LogError(Zv1Exception error)
    {
        if (_logger == null) return;

        var message = error.NodeId != null
            ? $"[{error.NodeType ?? "Node"}:{error.NodeId}] {error.Message}"
            : error.Message;

        switch (error.Severity)
        {
            case ErrorSeverity.Info:
                _logger.LogInformation(error, message);
                break;
            case ErrorSeverity.Warning:
                _logger.LogWarning(error, message);
                break;
            case ErrorSeverity.Error:
                _logger.LogError(error, message);
                break;
            case ErrorSeverity.Critical:
                _logger.LogCritical(error, message);
                break;
        }
    }
}

/// <summary>
/// Summary of recorded errors.
/// </summary>
public record ErrorSummary
{
    /// <summary>Gets the total number of errors.</summary>
    public int TotalErrors { get; init; }

    /// <summary>Gets error counts by severity.</summary>
    public Dictionary<ErrorSeverity, int> BySeverity { get; init; } = new();

    /// <summary>Gets error counts by type.</summary>
    public Dictionary<ErrorType, int> ByType { get; init; } = new();

    /// <summary>Gets error counts by node ID.</summary>
    public Dictionary<string, int> ByNode { get; init; } = new();
}
