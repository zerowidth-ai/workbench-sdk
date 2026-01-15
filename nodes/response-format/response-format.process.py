"""
Process function for the Response Format node.
Outputs a response_format object, either from the input or from the settings.
"""
from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": inputs.get("name", settings.get("name")),
                "strict": inputs.get("strict", settings.get("strict")),
                "schema": inputs.get("schema", settings.get("schema"))
            }
        } 
    }
