"""
Process function for the Get Object Property node.
Extracts a specific property value from an object by key name.
"""
from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    object_input = inputs.get("object")
    key = inputs.get("key")
    default_value = settings.get("default_value")
    
    # Validate inputs
    if not isinstance(object_input, dict):
        return {
            "value": default_value,
            "exists": False,
            "key": key or ""
        }
    
    if not isinstance(key, str):
        return {
            "value": default_value,
            "exists": False,
            "key": key or ""
        }
    
    # Check if property exists
    exists = key in object_input
    value = object_input.get(key, default_value) if exists else default_value
    
    return {
        "value": value,
        "exists": exists,
        "key": key
    }
