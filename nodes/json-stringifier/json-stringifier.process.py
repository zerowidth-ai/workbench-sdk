from typing import Any
import json

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the JSON Stringifier node.
    Converts an object or array to a JSON string.
    """
    value = inputs.get("value")
    json_string = ""
    error = ""
    success = False
    
    try:
        pretty = settings.get("pretty", False)
        indent = int(settings.get("indent", 2)) if pretty else None
        
        # Set separators to match JavaScript's JSON.stringify output
        # JavaScript doesn't add spaces after colons and commas by default
        if not pretty:
            json_string = json.dumps(value, indent=indent, separators=(',', ':'))
        else:
            json_string = json.dumps(value, indent=indent)
            
        success = True
    except Exception as e:
        error = str(e)
        json_string = "{}"
    
    return {
        "json": json_string,
        "error": error,
        "success": success
    } 