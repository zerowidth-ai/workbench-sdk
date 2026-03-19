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
    Process function for the JSON Parser node.
    Parses a JSON string into an object or array.
    """
    json_string = inputs.get("json", "")
    value = None
    error = ""
    success = False
    
    try:
        value = json.loads(json_string)
        success = True
        
        # For successful parsing, include all fields
        return {
            "value": value,
            "error": error,
            "success": success
        }
    except Exception as e:
        error = str(e)

        # Try to parse the default value
        try:
            value = json.loads(settings.get("default_value", "{}"))
        except Exception:
            value = {}

        return {
            "value": value,
            "error": error,
            "success": success,
        } 