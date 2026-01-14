"""
Type system for the zv1 engine.

This module provides:
- Custom type validation using JSON Schema
- Type checking for node inputs/outputs
- Type conversion utilities
- Support for union types (e.g., "string or message")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError as JsonSchemaValidationError

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    JsonSchemaValidationError = Exception  # type: ignore

from src.helpers import get_types_dir

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Type converter functions for custom types
TypeConverter = Callable[[Any], str]
TypeConverters = dict[str, TypeConverter]


class TypeInfo:
    """
    Information about a custom type including validator and converters.
    """

    def __init__(
        self,
        name: str,
        schema: dict[str, Any],
        validator: Draft7Validator | None = None,
        converters: TypeConverters | None = None,
    ) -> None:
        self.name = name
        self.schema = schema
        self.validator = validator
        self.converters = converters or {}

    def validate(self, value: Any) -> bool:
        """Validate a value against this type's schema."""
        if self.validator is None:
            return True
        try:
            self.validator.validate(value)
            return True
        except JsonSchemaValidationError:
            return False

    def to_string(self, value: Any, separator: str = "\n\n") -> str:
        """Convert a value of this type to string."""
        if "to_string" in self.converters:
            return self.converters["to_string"](value)
        return str(value) if value is not None else ""


# Built-in type converters
def conversation_to_string(value: list[dict[str, Any]], separator: str = "\n\n") -> str:
    """Convert a conversation (list of messages) to a string."""
    if not isinstance(value, list):
        return str(value) if value is not None else ""

    parts: list[str] = []
    for msg in value:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # Handle content arrays
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            content = "".join(text_parts)

        parts.append(f"{role}: {content}")

    return separator.join(parts)


def message_to_string(value: dict[str, Any], separator: str = "\n\n") -> str:
    """Convert a message to a string."""
    if not isinstance(value, dict):
        return str(value) if value is not None else ""

    role = value.get("role", "unknown")
    content = value.get("content", "")

    # Handle content arrays
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        content = "".join(text_parts)

    return f"{role}: {content}"


# Default converters for built-in custom types
DEFAULT_CONVERTERS: dict[str, TypeConverters] = {
    "conversation": {"to_string": conversation_to_string},
    "message": {"to_string": message_to_string},
}


async def load_custom_types(types_dir: Path | None = None) -> dict[str, TypeInfo]:
    """
    Load custom type configurations from the types directory.

    Args:
        types_dir: Path to types directory. Defaults to SDK types dir.

    Returns:
        Dict mapping type names to TypeInfo objects.
    """
    if types_dir is None:
        types_dir = get_types_dir()

    custom_types: dict[str, TypeInfo] = {}

    if not types_dir.exists():
        logger.warning(f"Types directory not found: {types_dir}")
        return custom_types

    for type_file in types_dir.glob("*.json"):
        type_name = type_file.stem

        try:
            with open(type_file) as f:
                schema = json.load(f)

            # Create validator if jsonschema is available
            validator = None
            if HAS_JSONSCHEMA:
                validator = Draft7Validator(schema)

            # Get converters (default or custom)
            converters = DEFAULT_CONVERTERS.get(type_name, {})

            custom_types[type_name] = TypeInfo(
                name=type_name,
                schema=schema,
                validator=validator,
                converters=converters,
            )

            logger.debug(f"Loaded custom type: {type_name}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse type schema {type_file}: {e}")
        except Exception as e:
            logger.error(f"Failed to load type {type_name}: {e}")

    return custom_types


def type_check(
    value: Any,
    type_str: str,
    custom_types: dict[str, TypeInfo] | None = None,
    debug: bool = False,
) -> bool:
    """
    Check if a value matches a given type.

    Handles basic types, custom types, and type unions.

    Args:
        value: The value to check.
        type_str: The expected type (e.g., "string", "number", "string or message").
        custom_types: Dict of custom type validators.
        debug: Whether to log debug messages.

    Returns:
        True if the value matches the type.
    """
    if debug:
        logger.debug(f"Type checking value against type '{type_str}': {value}")

    # Null values pass all type checks
    if value is None:
        if debug:
            logger.debug("Null value passes type check")
        return True

    type_str = type_str.lower().strip()

    # Any type always passes
    if type_str == "any":
        if debug:
            logger.debug("'any' type always passes")
        return True

    # Handle union types (e.g., "string or message")
    if " or " in type_str:
        type_options = [t.strip() for t in type_str.split(" or ")]
        if debug:
            logger.debug(f"Union type with options: {type_options}")
        return any(
            type_check(value, t, custom_types, debug=False) for t in type_options
        )

    # Handle string that looks like a number
    if type_str == "number" and isinstance(value, str):
        try:
            float(value)
            if debug:
                logger.debug("String to number conversion check: passed")
            return True
        except ValueError:
            if debug:
                logger.debug("String to number conversion check: failed")
            return False

    # Handle array type
    if type_str == "array":
        is_array = isinstance(value, list)
        if debug:
            logger.debug(f"Array type check: {'passed' if is_array else 'failed'}")
        return is_array

    # Handle "array of X" type
    if type_str.startswith("array of "):
        if not isinstance(value, list):
            if debug:
                logger.debug("Failed array check for 'array of' type")
            return False

        # Extract item type (remove trailing 's' for plurals)
        item_type = type_str[9:].rstrip("s")
        if debug:
            logger.debug(f"Checking each item in array against type: {item_type}")

        return all(
            type_check(item, item_type, custom_types, debug=False) for item in value
        )

    # Check custom types
    if custom_types and type_str in custom_types:
        type_info = custom_types[type_str]
        result = type_info.validate(value)
        if debug:
            logger.debug(
                f"Custom type '{type_str}' validation: {'passed' if result else 'failed'}"
            )
        return result

    # Basic type checks
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
    }

    if type_str in type_map:
        expected_type = type_map[type_str]
        # Special case: bool is a subclass of int in Python
        if type_str == "number" and isinstance(value, bool):
            return False
        result = isinstance(value, expected_type)
        if debug:
            logger.debug(
                f"Basic type check ({type(value).__name__} vs {type_str}): "
                f"{'passed' if result else 'failed'}"
            )
        return result

    # Fallback: compare with Python type name
    result = type(value).__name__ == type_str
    if debug:
        logger.debug(
            f"Fallback type check ({type(value).__name__} === {type_str}): "
            f"{'passed' if result else 'failed'}"
        )
    return result


def convert_type(
    value: Any,
    type_str: str,
    custom_types: dict[str, TypeInfo] | None = None,
    method: str = "to_string",
    separator: str = "\n\n",
) -> Any:
    """
    Convert a value of a given type using type converters.

    Args:
        value: The value to convert.
        type_str: The type name.
        custom_types: Dict of custom type info.
        method: Conversion method to use (default: 'to_string').
        separator: Separator for to_string (default: '\n\n').

    Returns:
        Converted value.
    """
    if value is None:
        return ""

    type_str = type_str.lower().strip()

    # Check if we have a converter for this custom type
    if custom_types and type_str in custom_types:
        type_info = custom_types[type_str]
        converters = type_info.converters

        # Try the specified method first
        if method in converters:
            if method == "to_string":
                # to_string converters may accept a separator
                try:
                    return converters[method](value, separator)
                except TypeError:
                    return converters[method](value)
            return converters[method](value)

        # Fallback to to_string if method not found
        if "to_string" in converters:
            try:
                return converters["to_string"](value, separator)
            except TypeError:
                return converters["to_string"](value)

    # Fallback to default string conversion
    return str(value)


def convert_import_to_node_type(
    import_def: dict[str, Any],
    parent_engine: Any = None,
) -> dict[str, Any]:
    """
    Convert an import definition into a node type configuration.

    Args:
        import_def: The import definition from the flow.
        parent_engine: The parent engine instance (for nested processing).

    Returns:
        A node type configuration dict with 'config' and 'process' keys.
    """
    logger.debug(f"Converting import {import_def.get('id')} to node type")

    # Process nested imports if present
    processed_def = {**import_def}
    if import_def.get("imports"):
        logger.debug(f"Processing {len(import_def['imports'])} nested imports")
        # Nested imports would be processed recursively here
        # This is handled by the engine when loading

    # Filter out debug-only nodes
    nodes = [n for n in processed_def.get("nodes", []) if not n.get("debug_only")]
    processed_def["nodes"] = nodes

    # Find input and output nodes
    input_nodes = [
        n
        for n in nodes
        if n.get("type") in ("input-chat", "input-prompt", "input-data")
    ]
    output_nodes = [n for n in nodes if n.get("type") in ("output-chat", "output-data")]

    logger.debug(
        f"Found {len(input_nodes)} input nodes and {len(output_nodes)} output nodes"
    )

    # Build inputs configuration
    inputs: list[dict[str, Any]] = []
    for node in input_nodes:
        node_type = node.get("type")
        settings = node.get("settings", {})

        if node_type == "input-data":
            inputs.append(
                {
                    "name": settings.get("key", "data"),
                    "display_name": f"Data: {settings.get('key', 'value')}",
                    "type": settings.get("type", "any"),
                    "required": True,
                    "is_data_input": True,
                    "description": settings.get("description", "Imported data input"),
                }
            )
        elif node_type == "input-chat":
            inputs.append(
                {
                    "name": settings.get("key", "chat"),
                    "display_name": "Chat",
                    "type": "conversation",
                    "required": True,
                    "is_chat_input": True,
                    "description": "Chat messages to process",
                }
            )
        else:  # input-prompt
            inputs.append(
                {
                    "name": settings.get("key", "prompt"),
                    "display_name": "Prompt",
                    "type": "string",
                    "required": True,
                    "is_prompt_input": True,
                    "description": "Prompt input",
                }
            )

    # Build outputs configuration
    outputs: list[dict[str, Any]] = []
    for node in output_nodes:
        node_type = node.get("type")
        settings = node.get("settings", {})

        if node_type == "output-data":
            outputs.append(
                {
                    "name": settings.get("key", "data"),
                    "display_name": f"Data: {settings.get('key', 'value')}",
                    "type": settings.get("type", "any"),
                    "description": settings.get("description", "Imported data output"),
                }
            )
        else:  # output-chat
            outputs.append(
                {
                    "name": settings.get("key", "chat"),
                    "display_name": "Response",
                    "type": "message",
                    "description": "Chat response output",
                }
            )

    # Check if any node accepts plugins
    accepts_plugins = any(n.get("type") == "input-plugins" for n in nodes)

    return {
        "config": {
            "display_name": processed_def.get("display_name", "Imported Flow"),
            "description": processed_def.get("description", "An imported flow"),
            "category": "imported",
            "is_constant": True,
            "is_plugin": True,
            "is_import": True,
            "accepts_plugins": accepts_plugins,
            "import_id": processed_def.get("importId"),
            "requested_snapshot": processed_def.get("requestedSnapshot"),
            "inputs": inputs,
            "outputs": outputs,
            "import_definition": processed_def,
        },
        "process": None,  # Process function created at runtime by engine
    }
