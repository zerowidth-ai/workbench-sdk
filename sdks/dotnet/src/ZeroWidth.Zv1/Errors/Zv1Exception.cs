namespace ZeroWidth.Zv1.Errors;

/// <summary>
/// Severity levels for errors.
/// </summary>
public enum ErrorSeverity
{
    /// <summary>Informational message.</summary>
    Info,
    /// <summary>Warning that doesn't stop execution.</summary>
    Warning,
    /// <summary>Error that may affect execution.</summary>
    Error,
    /// <summary>Critical error that stops execution.</summary>
    Critical
}

/// <summary>
/// Types of errors that can occur during execution.
/// </summary>
public enum ErrorType
{
    /// <summary>Error in node configuration.</summary>
    NodeError,
    /// <summary>Error in flow structure.</summary>
    FlowError,
    /// <summary>Input/output validation error.</summary>
    ValidationError,
    /// <summary>Operation timed out.</summary>
    TimeoutError,
    /// <summary>Resource not found or unavailable.</summary>
    ResourceError,
    /// <summary>Integration/API error.</summary>
    IntegrationError,
    /// <summary>Unknown or general error.</summary>
    Unknown
}

/// <summary>
/// Base exception class for all zv1 errors.
/// </summary>
public class Zv1Exception : Exception
{
    /// <summary>Gets the error type.</summary>
    public ErrorType ErrorType { get; }

    /// <summary>Gets the error severity.</summary>
    public ErrorSeverity Severity { get; }

    /// <summary>Gets the node ID where the error occurred, if applicable.</summary>
    public string? NodeId { get; }

    /// <summary>Gets the node type where the error occurred, if applicable.</summary>
    public string? NodeType { get; }

    /// <summary>Gets additional context about the error.</summary>
    public IDictionary<string, object>? Context { get; }

    /// <summary>
    /// Initializes a new instance of the Zv1Exception class.
    /// </summary>
    public Zv1Exception(
        string message,
        ErrorType errorType = ErrorType.Unknown,
        ErrorSeverity severity = ErrorSeverity.Error,
        string? nodeId = null,
        string? nodeType = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, innerException)
    {
        ErrorType = errorType;
        Severity = severity;
        NodeId = nodeId;
        NodeType = nodeType;
        Context = context;
    }
}

/// <summary>
/// Exception thrown when a node fails during execution.
/// </summary>
public class NodeException : Zv1Exception
{
    public NodeException(
        string message,
        string? nodeId = null,
        string? nodeType = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.NodeError, ErrorSeverity.Error, nodeId, nodeType, context, innerException)
    {
    }
}

/// <summary>
/// Exception thrown when flow structure is invalid.
/// </summary>
public class FlowException : Zv1Exception
{
    public FlowException(
        string message,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.FlowError, ErrorSeverity.Error, null, null, context, innerException)
    {
    }
}

/// <summary>
/// Exception thrown when input/output validation fails.
/// </summary>
public class ValidationException : Zv1Exception
{
    /// <summary>Gets the field that failed validation.</summary>
    public string? Field { get; }

    public ValidationException(
        string message,
        string? field = null,
        string? nodeId = null,
        string? nodeType = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.ValidationError, ErrorSeverity.Error, nodeId, nodeType, context, innerException)
    {
        Field = field;
    }
}

/// <summary>
/// Exception thrown when an operation times out.
/// </summary>
public class TimeoutException : Zv1Exception
{
    /// <summary>Gets the timeout duration in milliseconds.</summary>
    public int TimeoutMs { get; }

    public TimeoutException(
        string message,
        int timeoutMs,
        string? nodeId = null,
        string? nodeType = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.TimeoutError, ErrorSeverity.Error, nodeId, nodeType, context, innerException)
    {
        TimeoutMs = timeoutMs;
    }
}

/// <summary>
/// Exception thrown when a resource is not found or unavailable.
/// </summary>
public class ResourceException : Zv1Exception
{
    /// <summary>Gets the resource identifier.</summary>
    public string? ResourceId { get; }

    public ResourceException(
        string message,
        string? resourceId = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.ResourceError, ErrorSeverity.Error, null, null, context, innerException)
    {
        ResourceId = resourceId;
    }
}

/// <summary>
/// Exception thrown when an integration/API call fails.
/// </summary>
public class IntegrationException : Zv1Exception
{
    /// <summary>Gets the integration name.</summary>
    public string? Integration { get; }

    /// <summary>Gets the HTTP status code, if applicable.</summary>
    public int? StatusCode { get; }

    public IntegrationException(
        string message,
        string? integration = null,
        int? statusCode = null,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, ErrorType.IntegrationError, ErrorSeverity.Error, null, null, context, innerException)
    {
        Integration = integration;
        StatusCode = statusCode;
    }
}
