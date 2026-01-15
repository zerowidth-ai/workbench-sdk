"""
Error Management for the zv1 Flow Engine.

This module provides centralized error handling with:
- Custom exception hierarchy
- Error event creation for callbacks
- Execution context enrichment
- Error type classification
"""

from __future__ import annotations

import time
from collections.abc import Awaitable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Union


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    RECOVERABLE = "recoverable"
    FATAL = "fatal"


class ErrorType(str, Enum):
    """Error type classification."""

    NODE = "node"
    FLOW = "flow"
    SYSTEM = "system"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    RESOURCE = "resource"


@dataclass
class ErrorDetails:
    """Structured error details."""

    message: str
    timestamp: float = field(default_factory=time.time)
    execution_id: str | None = None
    node_id: str | None = None
    node_type: str | None = None
    field_name: str | None = None  # Renamed from 'field' to avoid shadowing dataclasses.field
    resource_type: str | None = None
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorEvent:
    """Error event structure for callbacks."""

    event: str = "error"
    type: ErrorType = ErrorType.NODE
    error: Exception | None = None
    error_details: ErrorDetails | None = None
    execution_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


class Zv1Error(Exception):
    """Base exception for all zv1 errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.SYSTEM,
        error_details: ErrorDetails | None = None,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.error_details = error_details or ErrorDetails(message=message)
        self.execution_id = execution_id
        self.context = context or {}
        self.original_error = original_error

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "message": str(self),
            "error_type": self.error_type.value,
            "execution_id": self.execution_id,
            "error_details": {
                "message": self.error_details.message,
                "timestamp": self.error_details.timestamp,
                "node_id": self.error_details.node_id,
                "node_type": self.error_details.node_type,
                "severity": self.error_details.severity.value,
            }
            if self.error_details
            else None,
            "context": self.context,
        }


class NodeError(Zv1Error):
    """Error during node execution."""

    def __init__(
        self,
        message: str,
        node_id: str,
        node_type: str,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        details = ErrorDetails(
            message=message,
            node_id=node_id,
            node_type=node_type,
            severity=ErrorSeverity.RECOVERABLE,
            execution_id=execution_id,
        )
        super().__init__(
            message=message,
            error_type=ErrorType.NODE,
            error_details=details,
            execution_id=execution_id,
            context=context,
            original_error=original_error,
        )
        self.node_id = node_id
        self.node_type = node_type


class FlowError(Zv1Error):
    """Error related to flow structure or validation."""

    def __init__(
        self,
        message: str,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        details = ErrorDetails(
            message=message,
            severity=ErrorSeverity.FATAL,
            execution_id=execution_id,
        )
        super().__init__(
            message=message,
            error_type=ErrorType.FLOW,
            error_details=details,
            execution_id=execution_id,
            context=context,
            original_error=original_error,
        )


class ValidationError(Zv1Error):
    """Input/output validation error."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        details = ErrorDetails(
            message=message,
            field_name=field_name,
            severity=ErrorSeverity.FATAL,
            execution_id=execution_id,
        )
        super().__init__(
            message=message,
            error_type=ErrorType.VALIDATION,
            error_details=details,
            execution_id=execution_id,
            context=context,
            original_error=original_error,
        )
        self.field_name = field_name


class TimeoutError(Zv1Error):  # noqa: A001 - Intentionally shadows builtin
    """Flow execution timeout error."""

    def __init__(
        self,
        message: str = "Flow execution timed out",
        timeout_ms: int | None = None,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        details = ErrorDetails(
            message=message,
            severity=ErrorSeverity.FATAL,
            execution_id=execution_id,
            extra={"timeout_ms": timeout_ms} if timeout_ms else {},
        )
        super().__init__(
            message=message,
            error_type=ErrorType.TIMEOUT,
            error_details=details,
            execution_id=execution_id,
            context=context,
        )
        self.timeout_ms = timeout_ms


class ResourceError(Zv1Error):
    """Resource allocation or access error."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        execution_id: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        details = ErrorDetails(
            message=message,
            resource_type=resource_type,
            severity=ErrorSeverity.FATAL,
            execution_id=execution_id,
        )
        super().__init__(
            message=message,
            error_type=ErrorType.RESOURCE,
            error_details=details,
            execution_id=execution_id,
            context=context,
            original_error=original_error,
        )
        self.resource_type = resource_type


# Type alias for error callback
ErrorCallback = Union[Callable[[ErrorEvent], None], Callable[[ErrorEvent], Awaitable[None]]]


class ErrorManager:
    """
    Centralized error handling utility for the Flow Engine.

    Handles:
    - Creating consistent error structures
    - Invoking on_error callbacks
    - Enriching errors with execution context
    - Managing error types and severity levels
    """

    def __init__(
        self,
        on_error: ErrorCallback | None = None,
        execution_id: str | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the ErrorManager.

        Args:
            on_error: Optional callback invoked when errors occur.
            execution_id: Unique identifier for this execution.
            execution_context: Additional context about the execution.
        """
        self.on_error = on_error
        self.execution_id = execution_id
        self.execution_context = execution_context or {}

    def update_execution_context(self, context: dict[str, Any]) -> None:
        """
        Update the execution context with new information.

        Args:
            context: New context to merge with existing context.
        """
        self.execution_context = {**self.execution_context, **context}

    def _create_error_event(
        self,
        error_type: ErrorType,
        error_details: ErrorDetails,
        original_error: Exception | None = None,
    ) -> ErrorEvent:
        """Create an error event structure for callbacks."""
        return ErrorEvent(
            event="error",
            type=error_type,
            error=original_error or Exception(error_details.message),
            error_details=error_details,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
        )

    async def _invoke_callback(self, error_event: ErrorEvent) -> None:
        """Invoke the error callback if provided."""
        if self.on_error is None:
            return

        try:
            result = self.on_error(error_event)
            # Handle both sync and async callbacks
            if hasattr(result, "__await__"):
                await result
        except Exception as callback_error:
            # Don't let callback errors interfere with main error
            import warnings

            warnings.warn(f"Error in on_error callback: {callback_error}", stacklevel=2)

    def throw_error(
        self,
        error_type: ErrorType,
        error_details: ErrorDetails,
        original_error: Exception | None = None,
    ) -> None:
        """
        Throw an error with full context.

        Args:
            error_type: Type of error.
            error_details: Specific details about the error.
            original_error: Original exception if one exists.

        Raises:
            Zv1Error: Enriched error with context.
        """
        error_details.execution_id = self.execution_id
        error_details.timestamp = time.time()

        error_event = self._create_error_event(error_type, error_details, original_error)

        # Note: Callback invocation in sync context
        # For async callback support, use throw_error_async
        if self.on_error is not None:
            try:
                result = self.on_error(error_event)
                if hasattr(result, "__await__"):
                    import warnings

                    warnings.warn(
                        "Async callback provided but throw_error called synchronously. "
                        "Use throw_error_async for async callbacks.",
                        stacklevel=2,
                    )
            except Exception as callback_error:
                import warnings

                warnings.warn(f"Error in on_error callback: {callback_error}", stacklevel=2)

        raise Zv1Error(
            message=error_details.message,
            error_type=error_type,
            error_details=error_details,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    async def throw_error_async(
        self,
        error_type: ErrorType,
        error_details: ErrorDetails,
        original_error: Exception | None = None,
    ) -> None:
        """
        Throw an error with full context (async version).

        Args:
            error_type: Type of error.
            error_details: Specific details about the error.
            original_error: Original exception if one exists.

        Raises:
            Zv1Error: Enriched error with context.
        """
        error_details.execution_id = self.execution_id
        error_details.timestamp = time.time()

        error_event = self._create_error_event(error_type, error_details, original_error)
        await self._invoke_callback(error_event)

        raise Zv1Error(
            message=error_details.message,
            error_type=error_type,
            error_details=error_details,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    # Convenience methods for common error types

    def throw_node_error(
        self,
        node_id: str,
        node_type: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Throw a node-specific error."""
        raise NodeError(
            message=message,
            node_id=node_id,
            node_type=node_type,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    def throw_flow_error(
        self,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Throw a flow-level error."""
        raise FlowError(
            message=message,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    def throw_system_error(
        self,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Throw a system-level error."""
        details = ErrorDetails(
            message=message,
            severity=ErrorSeverity.FATAL,
            execution_id=self.execution_id,
        )
        self.throw_error(ErrorType.SYSTEM, details, original_error)

    def throw_validation_error(
        self,
        field_name: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Throw a validation error."""
        raise ValidationError(
            message=message,
            field_name=field_name,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    def throw_timeout_error(
        self,
        message: str = "Flow execution timed out",
        timeout_ms: int | None = None,
    ) -> None:
        """Throw a timeout error."""
        raise TimeoutError(
            message=message,
            timeout_ms=timeout_ms or self.execution_context.get("timeout"),
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
        )

    def throw_resource_error(
        self,
        resource_type: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """Throw a resource exhaustion error."""
        raise ResourceError(
            message=message,
            resource_type=resource_type,
            execution_id=self.execution_id,
            context=self.execution_context.copy(),
            original_error=original_error,
        )

    def create_error_event_only(
        self,
        error_type: ErrorType,
        error_details: ErrorDetails,
        original_error: Exception | None = None,
    ) -> ErrorEvent:
        """
        Create an error event without throwing (useful for logging/monitoring).

        Args:
            error_type: Type of error.
            error_details: Error details.
            original_error: Original exception if one exists.

        Returns:
            Error event object.
        """
        error_details.execution_id = self.execution_id
        error_details.timestamp = time.time()

        error_event = self._create_error_event(error_type, error_details, original_error)

        # Invoke callback if provided (sync only)
        if self.on_error is not None:
            try:
                self.on_error(error_event)
            except Exception as callback_error:
                import warnings

                warnings.warn(f"Error in on_error callback: {callback_error}", stacklevel=2)

        return error_event

    @staticmethod
    def is_recoverable_error(error_type: ErrorType) -> bool:
        """
        Check if an error is recoverable based on its type.

        Args:
            error_type: Type of error to check.

        Returns:
            True if error is recoverable.
        """
        recoverable_types = {ErrorType.NODE, ErrorType.VALIDATION}
        fatal_types = {ErrorType.FLOW, ErrorType.SYSTEM, ErrorType.TIMEOUT, ErrorType.RESOURCE}

        if error_type in recoverable_types:
            return True
        if error_type in fatal_types:
            return False

        # Default to recoverable for unknown types
        return True
