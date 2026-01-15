from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Throw Error node.
    Raises an exception with a custom message and optional context.
    """
    message = inputs.get("message", "No error message provided")
    context = inputs.get("context", "")
    error_type = inputs.get("errorType", "CustomError")

    # Construct the full error message
    full_message = message
    if context:
        full_message += f"\n\nContext: {context}"

    # Create a custom exception class if needed
    if error_type != "CustomError":
        class CustomException(Exception):
            def __init__(self, message, context=None):
                super().__init__(message)
                self.context = context
                self.name = error_type
        
        # Raise the custom exception
        raise CustomException(full_message, context)
    else:
        # Use a standard exception with context
        exception = Exception(full_message)
        exception.context = context
        exception.name = error_type
        raise exception 