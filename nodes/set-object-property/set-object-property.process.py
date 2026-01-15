"""
Process function for the Set Object Property node.
Set or add a key-value pair to an object, returning a new object with the property set.
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
    value = inputs.get("value")
    overwrite = settings.get("overwrite", True)
    
    # Validate inputs - create empty object if input is null/undefined/invalid
    if not isinstance(object_input, dict):
        new_object = {}
        if key and isinstance(key, str):
            new_object[key] = value
        return {
            "object": new_object,
            "key": key or "",
            "value": value,
            "was_new": True
        }
    
    if not isinstance(key, str):
        return {
            "object": object_input,
            "key": key or "",
            "value": value,
            "was_new": False
        }
    
    # Check if property already exists
    was_new = key not in object_input
    
    # If overwrite is false and property exists, don't change it
    if not overwrite and not was_new:
        return {
            "object": object_input,
            "key": key,
            "value": object_input[key],
            "was_new": False
        }
    
    # Create new object with the property set
    new_object = object_input.copy()
    new_object[key] = value
    
    return {
        "object": new_object,
        "key": key,
        "value": value,
        "was_new": was_new
    }
