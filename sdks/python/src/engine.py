"""
zv1 Engine - Core class for executing node-based AI flows.

This module provides the main Zv1 class that handles:
- Flow loading and validation
- Node execution and propagation
- Input/output management
- Error handling and timeouts
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from src.cache import CacheManager
from src.errors import (
    ErrorManager,
    FlowError,
    NodeError,
    TimeoutError,
    Zv1Error,
)
from src.helpers import get_nodes_dir
from src.loaders import (
    detect_and_load_flow,
    load_integrations,
    load_nodes,
)
from src.types import TypeInfo, load_custom_types, type_check
from src.validators import validate_flow, validate_inputs, validate_keys

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class TimelineEntry:
    """Entry in the execution timeline."""

    node_id: str
    node_type: str
    inputs: dict[str, Any]
    settings: dict[str, Any]
    start_time: str
    end_time: str | None = None
    duration_ms: float | None = None
    outputs: dict[str, Any] | None = None
    status: str = "running"
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "inputs": self.inputs,
            "settings": self.settings,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "outputs": self.outputs,
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass
class ExecutionResult:
    """Result of flow execution."""

    outputs: dict[str, Any] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    cost_summary: dict[str, Any] | None = None
    inputs_missing_values: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""
    partial: bool = False
    terminal_nodes: list[dict[str, Any]] | None = None


class Zv1:
    """
    Core class for executing node-based AI flows.

    Handles node loading, input/output validation, and flow execution.
    """

    def __init__(
        self,
        flow: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Create a new Zv1 instance.

        Args:
            flow: The flow definition containing nodes and links.
            config: Configuration options and context for the engine.
        """
        self.flow = flow
        self.config = config or {}
        self.debug = self.config.get("debug", False)
        self.keys = self.config.get("keys", {})

        # Execution state
        self.execution_queue: list[dict[str, Any]] = []
        self.running_nodes: set[str] = set()
        self.completed_nodes: set[str] = set()
        self.max_concurrency = self.config.get("max_concurrency", 5)
        self.last_error: Exception | None = None

        self.max_plugin_calls = self.config.get("max_plugin_calls", 10)

        # Track executed node states
        self.executed_node_states: set[str] = set()
        self.queued_node_hashes: set[str] = set()

        # Timeout handling
        self.has_timed_out = False
        self._timeout_task: asyncio.Task[None] | None = None

        # Will be set during initialization
        self.nodes: dict[str, dict[str, Any]] = {}
        self.custom_types: dict[str, TypeInfo] = {}
        self.input_nodes: list[dict[str, Any]] = []
        self.entry_nodes: list[dict[str, Any]] = []
        self.cache = CacheManager()
        self.timeline: list[TimelineEntry] = []
        self.error_manager: ErrorManager | None = None

    async def initialize(self) -> None:
        """Initialize the engine (load nodes, validate flow, etc.)."""
        # Load nodes
        nodes_dir = Path(self.config.get("nodes_dir", get_nodes_dir()))
        self.nodes = await load_nodes(self.flow, nodes_dir, debug=self.debug)

        # Load custom types
        self.custom_types = await load_custom_types()

        # Load integrations if not provided
        if "integrations" not in self.config:
            self.config["integrations"] = await load_integrations(
                self.config, self.flow, debug=self.debug
            )

        # Initialize error manager
        execution_id = self.config.get("execution_id", str(uuid4()))
        self.error_manager = ErrorManager(
            on_error=self.config.get("on_error"),
            execution_id=execution_id,
            execution_context={
                "timeline": [],
                "node_count": len(self.flow.get("nodes", [])),
            },
        )

        self._log_debug(f"Loaded {len(self.nodes)} node types")
        self._log_debug(f"Loaded {len(self.custom_types)} custom types")

        # Sanitize the flow
        self._sanitize_flow()

        # Validate keys
        validate_keys(self.nodes, self.keys, debug=self.debug)

        # Validate flow structure
        self.input_nodes, self.entry_nodes = validate_flow(
            self.flow, self.nodes, debug=self.debug
        )

    @classmethod
    async def create(
        cls,
        flow: str | dict[str, Any] | bytes,
        config: dict[str, Any] | None = None,
    ) -> Zv1:
        """
        Create a new Zv1 instance (async factory method).

        Supports both legacy JSON files and new .zv1 files with hierarchical imports.

        Args:
            flow: File path (string), flow definition object, or ZIP data (bytes).
            config: Configuration options and context for the engine.

        Returns:
            Fully initialized Zv1 instance.

        Raises:
            FlowError: If flow cannot be loaded or is invalid.
        """
        try:
            # Load the flow
            loaded_flow = await detect_and_load_flow(flow)

            # Create engine instance
            engine = cls(loaded_flow, config)

            # Initialize
            await engine.initialize()

            return engine

        except FileNotFoundError as e:
            raise FlowError(f"Flow file not found: {e}") from e
        except json.JSONDecodeError as e:
            raise FlowError(f"Invalid JSON in flow file: {e}") from e
        except ValueError as e:
            raise FlowError(f"Invalid flow structure: {e}") from e
        except Exception as e:
            raise FlowError(f"Failed to create Zv1 instance: {e}") from e

    def _log_debug(self, *args: Any) -> None:
        """Log debug information."""
        if self.debug:
            message = " ".join(str(arg) for arg in args)
            logger.debug(f"[DEBUG] {message}")

    def _sanitize_flow(self) -> None:
        """Clean up the flow definition."""
        # Remove debug-only nodes
        self.flow["nodes"] = [
            n for n in self.flow.get("nodes", []) if not n.get("debug_only")
        ]

    def _create_execution_hash(
        self,
        node_id: str,
        inputs: dict[str, Any],
        settings: dict[str, Any],
    ) -> str:
        """Create a hash of node execution state."""
        state = {
            "id": node_id,
            "inputs": inputs or {},
            "settings": settings or {},
        }

        # For refiring nodes, add timestamp
        if self._has_refiring_input(node_id):
            node = next((n for n in self.flow["nodes"] if n["id"] == node_id), None)
            if node:
                node_def = self.nodes.get(node["type"], {})
                input_defs = node_def.get("config", {}).get("inputs", [])

                max_timestamp = 0
                for input_def in input_defs:
                    if input_def.get("allow_multiple") and input_def.get("refires"):
                        input_links = [
                            link
                            for link in self.flow.get("links", [])
                            if link["to"]["node_id"] == node_id
                            and link["to"]["port_name"] == input_def["name"]
                        ]
                        for link in input_links:
                            timestamp = self.cache.get_latest_timestamp(
                                node_id=link["from"]["node_id"],
                                port_name=link["from"]["port_name"],
                            )
                            if timestamp and timestamp > max_timestamp:
                                max_timestamp = timestamp

                state["timestamp"] = max_timestamp
        else:
            state["input_hash"] = json.dumps(inputs or {}, sort_keys=True)

        state_string = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_string.encode()).hexdigest()[:16]

    def _has_refiring_input(self, node_id: str) -> bool:
        """Check if node has any refiring inputs."""
        node = next((n for n in self.flow["nodes"] if n["id"] == node_id), None)
        if not node:
            return False

        node_def = self.nodes.get(node["type"])
        if not node_def:
            return False

        inputs = node_def.get("config", {}).get("inputs", [])
        return any(i.get("allow_multiple") and i.get("refires") for i in inputs)

    async def process_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single node.

        Args:
            node: The node to process.

        Returns:
            The outputs from the node.
        """
        self._log_debug(f"Processing node [{node['id']}] of type [{node['type']}]")

        node_def = self.nodes.get(node["type"])
        if not node_def:
            raise NodeError(
                message=f"Node type '{node['type']}' not found.",
                node_id=node["id"],
                node_type=node["type"],
            )

        # Apply default settings
        if not node.get("settings"):
            node["settings"] = {}

        config = node_def.get("config", {})
        for setting_def in config.get("settings", []):
            if (
                setting_def.get("default") is not None
                and node["settings"].get(setting_def["name"]) is None
            ):
                node["settings"][setting_def["name"]] = setting_def["default"]

        # Collect inputs
        inputs = self._collect_node_inputs(node, node_def)

        self._log_debug(f"Node [{node['id']}] inputs: {json.dumps(inputs, default=str)}")

        # Validate inputs
        validate_inputs(config, inputs, self.custom_types, debug=self.debug)

        # Execute the node
        outputs = await self._execute_node_core(node, inputs, node.get("settings", {}), node_def)

        # Track execution state
        execution_hash = self._create_execution_hash(node["id"], inputs, node.get("settings", {}))
        self.executed_node_states.add(execution_hash)

        self._log_debug(f"Node [{node['id']}] outputs: {json.dumps(outputs, default=str)}")

        # Handle updated settings
        if outputs.get("__updated_settings"):
            node["settings"] = {**node.get("settings", {}), **outputs["__updated_settings"]}
            del outputs["__updated_settings"]

        # Store outputs in cache
        for key, value in outputs.items():
            self.cache.set(node_id=node["id"], port_name=key, value=value)

        return outputs

    def _collect_node_inputs(
        self,
        node: dict[str, Any],
        node_def: dict[str, Any],
    ) -> dict[str, Any]:
        """Collect inputs for a node from the cache."""
        inputs: dict[str, Any] = {}
        config = node_def.get("config", {})
        input_defs = config.get("inputs", [])

        # Get links to this node
        node_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"]
        ]

        # Track connected inputs
        connected_inputs = {link["to"]["port_name"] for link in node_links}

        # Process connected inputs
        for link in node_links:
            input_name = link["to"]["port_name"]
            input_def = next((i for i in input_defs if i["name"] == input_name), None)

            if not input_def:
                continue

            from_node = link["from"]["node_id"]
            from_port = link["from"]["port_name"]

            if input_def.get("allow_multiple") and input_def.get("refires"):
                # Refiring input
                last_consumed = CacheManager.get_last_consumed(
                    node.get("settings"), input_name
                )

                if last_consumed == 0:
                    value = self.cache.get(node_id=from_node, port_name=from_port)
                    if value is not None:
                        inputs[input_name] = value
                else:
                    new_values = self.cache.get_new(
                        node_id=from_node,
                        port_name=from_port,
                        after_timestamp=last_consumed,
                    )
                    if new_values:
                        inputs[input_name] = new_values[0]

            elif input_def.get("allow_multiple"):
                # Multiple input (non-refiring)
                if self.cache.has(node_id=from_node, port_name=from_port):
                    if input_name not in inputs:
                        inputs[input_name] = []
                    value = self.cache.get(node_id=from_node, port_name=from_port)
                    if type_check(value, input_def.get("type", "any"), self.custom_types):
                        inputs[input_name].append(value)

            else:
                # Single value input
                if self.cache.has(node_id=from_node, port_name=from_port):
                    inputs[input_name] = self.cache.get(
                        node_id=from_node, port_name=from_port
                    )
                elif not input_def.get("required") and input_def.get("default") is not None:
                    inputs[input_name] = input_def["default"]

        # Handle unconnected inputs with defaults
        for input_def in input_defs:
            input_name = input_def["name"]
            if input_name not in connected_inputs and inputs.get(input_name) is None:
                if input_def.get("default") is not None:
                    inputs[input_name] = input_def["default"]

        return inputs

    async def _execute_node_core(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        settings: dict[str, Any],
        node_def: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a node's process function."""
        start_time = time.time()
        timeline_entry = TimelineEntry(
            node_id=node["id"],
            node_type=node["type"],
            inputs=copy.deepcopy(inputs),
            settings=copy.deepcopy(settings),
            start_time=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(start_time)),
        )

        try:
            # Call on_node_start callback
            if self.config.get("on_node_start"):
                await self._call_callback(
                    self.config["on_node_start"],
                    {
                        "node_id": node["id"],
                        "node_type": node["type"],
                        "timestamp": int(start_time * 1000),
                        "inputs": inputs,
                        "settings": settings,
                    },
                )

            # Add type and id to node config
            config = node_def.get("config", {})
            config["type"] = node["type"]
            config["id"] = node["id"]

            # Execute process function
            process_func = node_def.get("process")
            if process_func is None:
                raise NodeError(
                    message=f"No process function for node type '{node['type']}'",
                    node_id=node["id"],
                    node_type=node["type"],
                )

            outputs = await process_func(
                inputs=inputs,
                settings=settings,
                config=self.config,
                node_config=config,
            )

            end_time = time.time()
            timeline_entry.outputs = copy.deepcopy(outputs)
            timeline_entry.end_time = time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(end_time)
            )
            timeline_entry.duration_ms = (end_time - start_time) * 1000
            timeline_entry.status = "success"
            self.timeline.append(timeline_entry)

            # Call on_node_complete callback
            if self.config.get("on_node_complete"):
                await self._call_callback(
                    self.config["on_node_complete"],
                    {
                        "node_id": node["id"],
                        "node_type": node["type"],
                        "timestamp": int(end_time * 1000),
                        "inputs": inputs,
                        "outputs": outputs,
                        "settings": settings,
                    },
                )

            return outputs

        except Exception as e:
            end_time = time.time()
            timeline_entry.end_time = time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(end_time)
            )
            timeline_entry.duration_ms = (end_time - start_time) * 1000
            timeline_entry.status = "error"
            timeline_entry.error_message = str(e)
            self.timeline.append(timeline_entry)

            if self.error_manager:
                self.error_manager.update_execution_context(
                    {
                        "timeline": [t.to_dict() for t in self.timeline],
                        "node_count": len(self.flow.get("nodes", [])),
                        "nodes_executed": len(self.timeline),
                    }
                )

            raise NodeError(
                message=f"Node execution failed: {e}",
                node_id=node["id"],
                node_type=node["type"],
                original_error=e if isinstance(e, Exception) else None,
            ) from e

    async def _call_callback(
        self, callback: Callable[..., Any], data: dict[str, Any]
    ) -> None:
        """Call a callback, handling both sync and async."""
        try:
            result = callback(data)
            if hasattr(result, "__await__"):
                await result
        except Exception as e:
            logger.warning(f"Error in callback: {e}")

    async def propagate(self, current_node_id: str) -> None:
        """Propagate values through the graph from a node."""
        self._log_debug(f"Starting propagation from node [{current_node_id}]")

        if self.has_timed_out:
            if self.error_manager:
                self.error_manager.throw_timeout_error("Flow execution timed out.")

        # Find downstream nodes
        downstream_links = [
            link
            for link in self.flow.get("links", [])
            if link["from"]["node_id"] == current_node_id
            and self.cache.get(
                node_id=current_node_id, port_name=link["from"]["port_name"]
            )
            is not None
        ]

        for link in downstream_links:
            downstream_node = next(
                (n for n in self.flow["nodes"] if n["id"] == link["to"]["node_id"]),
                None,
            )

            if not downstream_node:
                continue

            # Skip plugin nodes linked as plugins
            node_def = self.nodes.get(downstream_node["type"], {})
            is_plugin = node_def.get("config", {}).get("is_plugin")
            is_linked_as_plugin = any(
                l.get("type") == "plugin" and l["from"]["node_id"] == downstream_node["id"]
                for l in self.flow.get("links", [])
            )

            if is_plugin and is_linked_as_plugin:
                continue

            # Check if node is ready
            if self._is_node_ready(downstream_node):
                self._add_to_execution_queue(downstream_node)

    def _is_node_ready(self, node: dict[str, Any]) -> bool:
        """Check if a node is ready to execute."""
        node_def = self.nodes.get(node["type"], {})
        input_defs = node_def.get("config", {}).get("inputs", [])

        # Get links to this node
        node_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"]
        ]

        # Group by input name
        links_by_input: dict[str, list[dict[str, Any]]] = {}
        for link in node_links:
            port_name = link["to"]["port_name"]
            if port_name not in links_by_input:
                links_by_input[port_name] = []
            links_by_input[port_name].append(link)

        # Check each input
        for input_name, links in links_by_input.items():
            input_def = next((i for i in input_defs if i["name"] == input_name), None)
            if not input_def:
                continue

            if input_def.get("allow_multiple") and input_def.get("refires"):
                # Refiring input - needs at least one new value
                last_consumed = CacheManager.get_last_consumed(
                    node.get("settings"), input_name
                )

                has_ready = False
                for link in links:
                    if link.get("type") == "plugin":
                        continue

                    from_node = link["from"]["node_id"]
                    from_port = link["from"]["port_name"]

                    if last_consumed == 0:
                        has_entry = self.cache.has(node_id=from_node, port_name=from_port)
                        value = self.cache.get(node_id=from_node, port_name=from_port)
                        if has_entry and value is not None:
                            has_ready = True
                            break
                    else:
                        has_new = self.cache.has_new(
                            node_id=from_node,
                            port_name=from_port,
                            after_timestamp=last_consumed,
                        )
                        if has_new:
                            has_ready = True
                            break

                if not has_ready:
                    return False
            else:
                # Non-refiring - all links must be ready
                for link in links:
                    if link.get("type") == "plugin":
                        continue

                    from_node = link["from"]["node_id"]
                    from_port = link["from"]["port_name"]

                    has_entry = self.cache.has(node_id=from_node, port_name=from_port)

                    if input_def.get("required") and not has_entry:
                        return False

        return True

    def _add_to_execution_queue(self, node: dict[str, Any]) -> bool:
        """Add a node to the execution queue with duplicate checking."""
        node_def = self.nodes.get(node["type"])
        if not node_def:
            return False

        inputs = self._collect_node_inputs(node, node_def)
        execution_hash = self._create_execution_hash(
            node["id"], inputs, node.get("settings", {})
        )

        if execution_hash in self.executed_node_states:
            self._log_debug(
                f"Node [{node['id']}] already executed with identical state, skipping"
            )
            return False

        if execution_hash in self.queued_node_hashes:
            self._log_debug(
                f"Node [{node['id']}] already in queue, skipping"
            )
            return False

        self.queued_node_hashes.add(execution_hash)
        self.execution_queue.append(node)
        self._log_debug(f"Added node [{node['id']}] to execution queue")
        return True

    async def run(
        self,
        input_data: dict[str, Any] | None = None,
        timeout: int = 60000,
    ) -> ExecutionResult:
        """
        Run the flow and return the final output.

        Args:
            input_data: Data to inject into input nodes.
            timeout: Maximum execution time in milliseconds.

        Returns:
            ExecutionResult with outputs, timeline, and cost summary.
        """
        self._log_debug(f"Starting flow execution with timeout: {timeout}ms")
        input_data = input_data or {}

        # Clear state for this run
        self.executed_node_states.clear()
        self.queued_node_hashes.clear()
        self.execution_queue.clear()
        self.running_nodes.clear()
        self.completed_nodes.clear()
        self.timeline.clear()
        self.has_timed_out = False

        if self.error_manager:
            self.error_manager.update_execution_context(
                {"timeout": timeout, "start_time": time.time()}
            )

        # Set timeout
        async def timeout_handler() -> None:
            await asyncio.sleep(timeout / 1000)
            self.has_timed_out = True
            self._log_debug("Flow execution timed out")

        self._timeout_task = asyncio.create_task(timeout_handler())

        inputs_missing_values: list[dict[str, Any]] = []

        try:
            # Step 1: Add entry nodes to queue
            for node in self.entry_nodes:
                self._add_to_execution_queue(node)

            # Step 2: Setup and add input nodes
            for input_node in self.input_nodes:
                if not input_node.get("settings"):
                    input_node["settings"] = {}

                node_type = input_node["type"]
                settings = input_node.get("settings", {})

                if node_type == "input-data":
                    key = settings.get("key", "data")
                    value = input_data.get(key)

                    # Fallback mapping
                    if value is None and "data" in input_data and key != "data":
                        value = input_data["data"]

                    if value is None:
                        value = settings.get("default_value")

                    if value is not None:
                        node_copy = {
                            **input_node,
                            "settings": {**settings, "value": value},
                        }
                        self._add_to_execution_queue(node_copy)
                    else:
                        inputs_missing_values.append(
                            {"id": input_node["id"], "type": node_type, "key": key}
                        )

                elif node_type == "input-chat":
                    key = settings.get("key", "chat")
                    value = input_data.get(key)

                    if value is not None:
                        node_copy = {
                            **input_node,
                            "settings": {**settings, "messages": value},
                        }
                        self._add_to_execution_queue(node_copy)
                    else:
                        inputs_missing_values.append(
                            {"id": input_node["id"], "type": node_type, "key": key}
                        )

                elif node_type == "input-prompt":
                    key = settings.get("key", "prompt")
                    value = input_data.get(key)

                    if value is not None:
                        node_copy = {
                            **input_node,
                            "settings": {**settings, "prompt": value},
                        }
                        self._add_to_execution_queue(node_copy)
                    else:
                        inputs_missing_values.append(
                            {"id": input_node["id"], "type": node_type, "key": key}
                        )

            # Step 3: Process execution queue
            while self.execution_queue or self.running_nodes:
                if self.has_timed_out:
                    raise TimeoutError("Flow execution timed out.")

                # Launch nodes up to concurrency limit
                while self.execution_queue and len(self.running_nodes) < self.max_concurrency:
                    node = self.execution_queue.pop(0)
                    await self._launch_node(node)

                # Wait for completion
                if self.running_nodes:
                    await asyncio.sleep(0.01)  # Small delay to allow task switching

                    if self.last_error:
                        error = self.last_error
                        self.last_error = None
                        raise error

            # Step 4: Collect outputs
            output_nodes = [
                n
                for n in self.flow["nodes"]
                if self.nodes.get(n["type"], {}).get("config", {}).get("is_output")
            ]

            if not output_nodes:
                # Return partial results from terminal nodes
                terminal_outputs = self._get_terminal_outputs()
                return ExecutionResult(
                    partial=True,
                    message=(
                        "Completed with missing input values and output nodes."
                        if inputs_missing_values
                        else "Completed without output nodes."
                    ),
                    terminal_nodes=terminal_outputs,
                    timeline=[t.to_dict() for t in self.timeline],
                    inputs_missing_values=inputs_missing_values,
                    cost_summary=self._get_cost_summary(),
                )

            final_outputs = self._collect_final_outputs(output_nodes)

            return ExecutionResult(
                outputs=final_outputs,
                timeline=[t.to_dict() for t in self.timeline],
                cost_summary=self._get_cost_summary(),
                inputs_missing_values=inputs_missing_values,
                message=(
                    "Completed with missing input values."
                    if inputs_missing_values
                    else "Completed."
                ),
            )

        except Exception as e:
            if self._timeout_task:
                self._timeout_task.cancel()
            raise

        finally:
            if self._timeout_task:
                self._timeout_task.cancel()

    async def _launch_node(self, node: dict[str, Any]) -> None:
        """Launch a node for execution."""
        self.running_nodes.add(node["id"])

        # Remove from queued hashes
        node_def = self.nodes.get(node["type"])
        if node_def:
            inputs = self._collect_node_inputs(node, node_def)
            execution_hash = self._create_execution_hash(
                node["id"], inputs, node.get("settings", {})
            )
            self.queued_node_hashes.discard(execution_hash)

        try:
            await self.process_node(node)
            self.running_nodes.discard(node["id"])
            self.completed_nodes.add(node["id"])
            await self.propagate(node["id"])

        except Exception as e:
            self.running_nodes.discard(node["id"])
            self.last_error = e

    def _get_terminal_outputs(self) -> list[dict[str, Any]]:
        """Get outputs from terminal nodes (no outgoing connections)."""
        nodes_with_outgoing = {
            link["from"]["node_id"] for link in self.flow.get("links", [])
        }

        terminal_nodes = [
            n for n in self.flow["nodes"] if n["id"] not in nodes_with_outgoing
        ]

        results = []
        for node in terminal_nodes:
            node_config = self.nodes.get(node["type"], {}).get("config", {})
            outputs: dict[str, Any] = {}

            for output_def in node_config.get("outputs", []):
                value = self.cache.get(node_id=node["id"], port_name=output_def["name"])
                if value is not None:
                    outputs[output_def["name"]] = value

            if outputs:
                results.append(
                    {"node_id": node["id"], "type": node["type"], "outputs": outputs}
                )

        return results

    def _collect_final_outputs(
        self, output_nodes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Collect final outputs from output nodes."""
        final_outputs: dict[str, Any] = {}

        data_index = 0
        chat_index = 0

        for node in output_nodes:
            node_config = self.nodes.get(node["type"], {}).get("config", {})
            output_key = node.get("settings", {}).get("key")
            has_key = bool(output_key)

            for output_def in node_config.get("outputs", []):
                if not self.cache.has(node_id=node["id"], port_name=output_def["name"]):
                    continue

                value = self.cache.get(node_id=node["id"], port_name=output_def["name"])
                if value is None:
                    continue

                if node["type"] == "output-data":
                    if has_key:
                        final_outputs[output_key] = value
                    else:
                        final_outputs[f"data_{data_index}" if data_index else "data"] = value
                        data_index += 1

                elif node["type"] == "output-chat":
                    if has_key:
                        final_outputs[output_key] = value
                    else:
                        final_outputs[f"chat_{chat_index}" if chat_index else "chat"] = value
                        chat_index += 1

        return final_outputs

    def _get_cost_summary(self) -> dict[str, Any]:
        """Get cost summary from timeline."""
        total_cost = 0.0
        itemized: list[dict[str, Any]] = []

        for entry in self.timeline:
            if entry.outputs and entry.outputs.get("cost_total"):
                total_cost += entry.outputs["cost_total"]
                itemized.append(
                    {
                        "node_id": entry.node_id,
                        "node_type": entry.node_type,
                        "cost": entry.outputs["cost_total"],
                    }
                )

        return {"total_cost": round(total_cost, 8), "itemized": itemized}

    async def cleanup(self) -> None:
        """Clean up resources."""
        self._log_debug("Starting cleanup...")

        try:
            # Clean up integrations
            integrations = self.config.get("integrations", {})

            if "knowledge_base" in integrations:
                kb = integrations["knowledge_base"]
                if hasattr(kb, "disconnect"):
                    await kb.disconnect()

            # Clear cache
            self.cache.clear()
            self.timeline.clear()

            self._log_debug("Cleanup completed")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
