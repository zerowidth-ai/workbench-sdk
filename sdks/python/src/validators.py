"""
Validation utilities for the zv1 engine.

This module provides:
- API key validation for nodes
- Flow structure validation
- Input validation against node configurations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.errors import FlowError, ValidationError
from src.types import TypeInfo, type_check

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def is_oauth_key(key_value: Any) -> bool:
    """
    Check if a key value is an OAuth key structure.

    Args:
        key_value: The key value to check.

    Returns:
        True if the key is an OAuth key structure.
    """
    if not isinstance(key_value, dict):
        return False

    # OAuth keys have accessToken and onRefresh
    return "access_token" in key_value and "on_refresh" in key_value


def validate_keys(
    nodes: dict[str, dict[str, Any]],
    keys: dict[str, Any],
    debug: bool = False,
) -> None:
    """
    Validate keys for all nodes that specify `needs_key_from`.

    Args:
        nodes: Dict mapping node types to their definitions.
        keys: Dict of API keys.
        debug: Whether to log debug messages.

    Raises:
        ValidationError: If required keys are missing.
    """
    if debug:
        logger.debug("Validating required API keys for nodes...")

    for node_type, node_definition in nodes.items():
        config = node_definition.get("config", {})
        needs_key_from = config.get("needs_key_from")

        if not needs_key_from:
            continue

        # Normalize to list
        required_keys = (
            needs_key_from if isinstance(needs_key_from, list) else [needs_key_from]
        )

        # Find missing keys
        missing_keys: list[str] = []
        for key in required_keys:
            if key not in keys:
                missing_keys.append(key)
                continue

            key_value = keys[key]

            # OAuth keys are valid if they have the right structure
            if is_oauth_key(key_value):
                continue

            # For non-OAuth keys, they're valid if they exist

        if missing_keys:
            if debug:
                logger.debug(
                    f"Missing required keys for node type '{node_type}': "
                    f"{', '.join(missing_keys)}"
                )
            raise ValidationError(
                message=(
                    f"Node type '{node_type}' requires the following missing keys: "
                    f"{', '.join(missing_keys)}"
                ),
                field_name="keys",
            )

        if debug:
            logger.debug(f"All required keys for node type '{node_type}' are present.")

    if debug:
        logger.debug("Key validation completed successfully")


def validate_flow(
    flow: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    debug: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate flow structure and return input/entry nodes.

    Args:
        flow: The flow definition with 'nodes' and 'links'.
        nodes: Dict mapping node types to their definitions.
        debug: Whether to log debug messages.

    Returns:
        Tuple of (input_nodes, entry_nodes).

    Raises:
        FlowError: If flow structure is invalid.
    """
    flow_nodes = flow.get("nodes", [])
    flow_links = flow.get("links", [])

    # Validate all links reference existing nodes
    node_ids = {node["id"] for node in flow_nodes}
    invalid_links = [
        link
        for link in flow_links
        if link["from"]["node_id"] not in node_ids
        or link["to"]["node_id"] not in node_ids
    ]

    if invalid_links:
        if debug:
            logger.debug(
                f"Found invalid links referencing non-existent nodes: {invalid_links}"
            )
        invalid_desc = ", ".join(
            f"{link['from']['node_id']} -> {link['to']['node_id']}"
            for link in invalid_links
        )
        raise FlowError(
            f"Flow contains {len(invalid_links)} invalid link(s) referencing "
            f"non-existent nodes: {invalid_desc}"
        )

    # Find input nodes
    input_nodes = [
        node
        for node in flow_nodes
        if nodes.get(node["type"], {}).get("config", {}).get("is_input")
    ]

    # Find entry nodes (constant nodes without inputs, not linked as plugins)
    entry_nodes: list[dict[str, Any]] = []
    for node in flow_nodes:
        node_config = nodes.get(node["type"], {}).get("config", {})

        # Must be a constant node
        if not node_config.get("is_constant"):
            continue

        # Must not have any input connections
        has_inputs = any(link["to"]["node_id"] == node["id"] for link in flow_links)
        if has_inputs:
            continue

        # Exclude if it's a plugin linked as a plugin
        is_plugin = node_config.get("is_plugin")
        is_linked_as_plugin = any(
            link.get("type") == "plugin" and link["from"]["node_id"] == node["id"]
            for link in flow_links
        )
        if is_plugin and is_linked_as_plugin:
            continue

        entry_nodes.append(node)

    if debug:
        input_ids = ", ".join(n["id"] for n in input_nodes) if input_nodes else ""
        entry_ids = ", ".join(n["id"] for n in entry_nodes) if entry_nodes else ""
        logger.debug(
            f"Found {len(input_nodes)} input nodes"
            f"{': ' + input_ids if input_ids else ''}"
        )
        logger.debug(
            f"Found {len(entry_nodes)} entry nodes"
            f"{': ' + entry_ids if entry_ids else ''}"
        )

    # Ensure there's at least one entry point
    if not input_nodes and not entry_nodes:
        raise FlowError(
            "Flow must have at least one input node or constant node without "
            "inputs to start execution"
        )

    return input_nodes, entry_nodes


def validate_inputs(
    node_config: dict[str, Any],
    inputs: dict[str, Any],
    custom_types: dict[str, TypeInfo] | None = None,
    debug: bool = False,
) -> None:
    """
    Validate inputs against the node's configuration.

    Args:
        node_config: The node's configuration dict.
        inputs: The inputs dict to validate.
        custom_types: Dict of custom type validators.
        debug: Whether to log debug messages.

    Raises:
        ValidationError: If inputs are invalid.
    """
    if debug:
        logger.debug(f"Validating inputs against node config: {inputs}")

    display_name = node_config.get("display_name", "Node")
    input_defs = node_config.get("inputs", [])

    for input_def in input_defs:
        name = input_def.get("name")
        input_type = input_def.get("type", "any")
        required = input_def.get("required", False)
        value = inputs.get(name)

        # Check if required and missing
        if required and value is None:
            if debug:
                logger.debug(f"Validation error: Missing required input: {name}")
            raise ValidationError(
                message=f"{display_name} is missing required input: {name}",
                field_name=name,
            )

        # Check if type matches
        if value is not None and not type_check(value, input_type, custom_types):
            if debug:
                logger.debug(
                    f"Validation error: Type mismatch for input '{name}': "
                    f"Expected {input_type}, got {value}"
                )
            raise ValidationError(
                message=(
                    f"{display_name} has a type mismatch for input '{name}': "
                    f"Expected {input_type}, got {type(value).__name__}"
                ),
                field_name=name,
            )

        if debug:
            logger.debug(f"Input '{name}' validation passed")


def validate_outputs(
    node_config: dict[str, Any],
    outputs: dict[str, Any],
    custom_types: dict[str, TypeInfo] | None = None,
    debug: bool = False,
) -> None:
    """
    Validate outputs against the node's configuration.

    Args:
        node_config: The node's configuration dict.
        outputs: The outputs dict to validate.
        custom_types: Dict of custom type validators.
        debug: Whether to log debug messages.

    Raises:
        ValidationError: If outputs are invalid.
    """
    if debug:
        logger.debug(f"Validating outputs against node config: {outputs}")

    display_name = node_config.get("display_name", "Node")
    output_defs = node_config.get("outputs", [])

    for output_def in output_defs:
        name = output_def.get("name")
        output_type = output_def.get("type", "any")
        value = outputs.get(name)

        # Check if type matches (if value is present)
        if value is not None and not type_check(value, output_type, custom_types):
            if debug:
                logger.debug(
                    f"Validation warning: Type mismatch for output '{name}': "
                    f"Expected {output_type}, got {value}"
                )
            # Outputs are typically not as strict - just log a warning
            logger.warning(
                f"{display_name} output '{name}' type mismatch: "
                f"Expected {output_type}, got {type(value).__name__}"
            )

        if debug:
            logger.debug(f"Output '{name}' validation passed")
