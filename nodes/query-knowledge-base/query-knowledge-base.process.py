"""
Query Knowledge Base Node - Executes SQL queries against the knowledge base.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Query Knowledge Base node.
    """
    # Get knowledge base integration from engine (supports multiple backends)
    integrations = config.get("integrations", {})
    knowledge_base = integrations.get("knowledgeBase") or integrations.get("sqlite")

    if not knowledge_base:
        raise ValueError(
            "Knowledge base integration not found. Make sure a knowledge database is available."
        )

    query = inputs.get("query")
    params = inputs.get("params", [])
    operation = inputs.get("operation", "SELECT")

    if not query or not isinstance(query, str):
        raise ValueError("Query is required and must be a string")

    if not isinstance(params, list):
        raise ValueError("Parameters must be an array")

    # Validate operation type
    allowed_operations = ["SELECT", "INSERT", "UPDATE", "DELETE"]
    if operation.upper() not in allowed_operations:
        raise ValueError(
            f"Invalid operation type: {operation}. Must be one of: {', '.join(allowed_operations)}"
        )

    # Execute the query
    result = await knowledge_base.query(query, params, operation)

    return {
        "data": result.get("data"),
        "success": result.get("success"),
        "rowCount": result.get("rowCount"),
        "operation": result.get("operation"),
        "error": None,
    }
