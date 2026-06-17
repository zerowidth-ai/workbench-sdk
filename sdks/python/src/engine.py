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
from typing import TYPE_CHECKING, Any, Callable, Optional
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
from src.mcp import call_mcp_tool, fetch_mcp_tools, is_remote_mcp_tool
from src.types import TypeInfo, load_custom_types, type_check
from src.utilities.sanitize_api_call import sanitize_api_call_event
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
        self._abort_event: asyncio.Event | None = None
        self._abort_link_task: asyncio.Task[None] | None = None
        # Signal inherited from an ancestor engine, captured once at construction
        # (sub-engines receive the parent's via {**config}). A later run() must not
        # treat a prior run's own signal — which run() writes into config["signal"]
        # — as an ancestor, so we snapshot it here rather than re-reading config.
        self._inherited_signal: asyncio.Event | None = self.config.get("signal")

        # Will be set during initialization
        self.nodes: dict[str, dict[str, Any]] = {}
        self.custom_types: dict[str, TypeInfo] = {}
        self.input_nodes: list[dict[str, Any]] = []
        self.entry_nodes: list[dict[str, Any]] = []
        self.cache = CacheManager()
        self.timeline: list[TimelineEntry] = []
        self.error_manager: ErrorManager | None = None

        # LLM plugin mappings: node_id -> list of connected plugin node IDs
        self.llm_plugins: dict[str, list[str]] = {}

        # Conversation state for imported chat nodes: conversationKey -> list of messages
        self._conversation_state: dict[str, list[dict[str, Any]]] = {}

        # Track knowledge base files that need cleanup
        self._knowledge_files_to_cleanup: set[str] = set()

        # Event-based node completion signaling
        self._node_completion_resolvers: list[asyncio.Future[None]] = []

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

        # Bind API call emit helper for node process functions (e.g. http-request)
        config_ref = self.config

        async def _emit_api_call(raw_event: dict[str, Any]) -> None:
            if not config_ref.get("on_api_call"):
                return
            event = sanitize_api_call_event(raw_event)
            try:
                callback = config_ref["on_api_call"]
                result = callback(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

        self.config["_emit_api_call"] = _emit_api_call

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

        # Initialize LLM plugin mappings
        self._initialize_plugin_mappings()

        # Track knowledge base files for cleanup
        self._track_knowledge_files()

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

        # Check if this is a macro node - handle it specially (BEFORE accepts_plugins check)
        if config.get("is_macro"):
            self._log_debug(f"Node [{node['id']}] is a macro. Executing internal flow.")
            outputs = await self._process_macro_node(node, inputs, config)
        # Check if this is an LLM node that accepts plugins
        elif config.get("accepts_plugins"):
            self._log_debug(f"Node [{node['id']}] is an LLM with plugin support. Using _process_llm_node.")
            outputs = await self._process_llm_node(node, inputs, node_def)
        else:
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

    async def _process_macro_node(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        macro_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process a macro node by running its internal flow.

        Macro nodes have a macro_flow that defines their internal processing.
        This creates a child engine to run the internal flow.

        Args:
            node: The macro node to process.
            inputs: The collected inputs for the node.
            macro_config: The macro node's configuration (contains macro_flow).

        Returns:
            The outputs from the macro's internal flow.
        """
        self._log_debug(f"Processing macro node [{node['id']}] of type [{node['type']}]")

        # Get the macro_flow from the config
        macro_flow_def = macro_config.get("macro_flow")
        if not macro_flow_def:
            raise NodeError(
                message=f"Macro node '{node['type']}' has no macro_flow defined.",
                node_id=node["id"],
                node_type=node["type"],
            )

        # Create timeline entry for macro execution
        start_time = time.time()
        timeline_entry = TimelineEntry(
            node_id=node["id"],
            node_type=node["type"],
            inputs=copy.deepcopy(inputs),
            settings=copy.deepcopy(node.get("settings", {})),
            start_time=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(start_time)),
        )

        try:
            # Create the internal flow from macro_flow
            internal_flow = {
                "nodes": list(macro_flow_def.get("nodes", [])),
                "links": list(macro_flow_def.get("links", [])),
            }

            # Create child engine config - inherit from parent
            child_config = {
                **self.config,
                # Don't propagate callbacks to child engine unless explicitly requested
                "on_node_start": self.config.get("on_node_start") if self.config.get("include_internal_events") else None,
                "on_node_complete": self.config.get("on_node_complete") if self.config.get("include_internal_events") else None,
                "on_node_error": self.config.get("on_node_error") if self.config.get("include_internal_events") else None,
            }

            # Create internal engine
            internal_engine = Zv1(internal_flow, child_config)
            await internal_engine.initialize()

            # Map macro inputs to internal flow inputs
            # The macro's input config defines the expected inputs
            input_data: dict[str, Any] = {}
            for input_def in macro_config.get("inputs", []):
                input_name = input_def.get("name")
                if input_name and input_name in inputs:
                    input_data[input_name] = inputs[input_name]
                    self._log_debug(f"Mapped macro input '{input_name}' to internal flow")

            self._log_debug(f"Macro [{node['id']}] internal inputs: {list(input_data.keys())}")

            # Call on_node_start callback
            if self.config.get("on_node_start"):
                await self._call_callback(
                    self.config["on_node_start"],
                    {
                        "node_id": node["id"],
                        "node_type": node["type"],
                        "timestamp": int(start_time * 1000),
                        "inputs": inputs,
                        "settings": node.get("settings", {}),
                    },
                )

            # Execute the internal flow
            internal_result = await internal_engine.run(input_data)

            # Map internal outputs back to macro outputs
            macro_outputs: dict[str, Any] = {}

            # First try to get outputs from the result
            if internal_result.outputs:
                macro_outputs = internal_result.outputs.copy()

            # Also look for outputs based on the macro's output config
            # Macro outputs typically expect "output_{name}" nodes
            for output_def in macro_config.get("outputs", []):
                output_name = output_def.get("name")
                if output_name:
                    # Check if this output is already in the results
                    if output_name in macro_outputs:
                        continue

                    # Look for the output in the internal engine's cache
                    # Output nodes are typically named "output_{key}" in macros
                    output_node_id = f"output_{output_name}"
                    output_value = internal_engine.cache.get(node_id=output_node_id, port_name="value")
                    if output_value is not None:
                        macro_outputs[output_name] = output_value
                        self._log_debug(f"Got macro output '{output_name}' from internal cache")

            # Also check terminal nodes for outputs
            if internal_result.terminal_nodes:
                for terminal_node in internal_result.terminal_nodes:
                    if terminal_node.get("outputs"):
                        for out_name, out_value in terminal_node["outputs"].items():
                            if out_name not in macro_outputs:
                                macro_outputs[out_name] = out_value

            self._log_debug(f"Macro [{node['id']}] outputs: {list(macro_outputs.keys())}")

            # Complete timeline entry
            end_time = time.time()
            timeline_entry.outputs = copy.deepcopy(macro_outputs)
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
                        "outputs": macro_outputs,
                        "duration_ms": timeline_entry.duration_ms,
                    },
                )

            return macro_outputs

        except Exception as e:
            end_time = time.time()
            timeline_entry.end_time = time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(end_time)
            )
            timeline_entry.duration_ms = (end_time - start_time) * 1000
            timeline_entry.status = "error"
            timeline_entry.error_message = str(e)
            self.timeline.append(timeline_entry)

            # Call on_node_error callback
            if self.config.get("on_node_error"):
                await self._call_callback(
                    self.config["on_node_error"],
                    {
                        "node_id": node["id"],
                        "node_type": node["type"],
                        "timestamp": int(end_time * 1000),
                        "error": str(e),
                        "duration_ms": timeline_entry.duration_ms,
                    },
                )

            raise NodeError(
                message=f"Macro node execution failed: {e}",
                node_id=node["id"],
                node_type=node["type"],
                original_error=e if isinstance(e, Exception) else None,
            ) from e

    def _initialize_plugin_mappings(self) -> None:
        """
        Scan for plugin links and map LLM nodes to their plugin/tool nodes.

        This creates self.llm_plugins which maps each LLM node ID to a list
        of plugin node IDs connected to it via plugin links.
        """
        self.llm_plugins = {}
        for node in self.flow.get("nodes", []):
            node_config = self.nodes.get(node["type"], {}).get("config", {})
            if node_config.get("accepts_plugins"):
                # Find all plugin links where this node is the target
                plugin_node_ids = [
                    link["from"]["node_id"]
                    for link in self.flow.get("links", [])
                    if link.get("type") == "plugin" and link["to"]["node_id"] == node["id"]
                ]
                self.llm_plugins[node["id"]] = plugin_node_ids
                if plugin_node_ids:
                    self._log_debug(
                        f"LLM node [{node['id']}] has {len(plugin_node_ids)} plugins: {plugin_node_ids}"
                    )

    def _is_local_node_plugin(self, node: dict[str, Any]) -> bool:
        """Check if a node is a local plugin (not MCP or manual tool)."""
        node_config = self.nodes.get(node["type"], {}).get("config", {})
        return node_config.get("is_plugin") or node_config.get("is_macro") or node_config.get("is_import")

    async def execute_plugin_in_parent_context(
        self, plugin_node: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a plugin node in the parent context with all its dependencies.

        This allows plugins to be called from internal engines (macros/imports)
        while maintaining their connections in the parent flow.

        Args:
            plugin_node: The plugin node to execute.
            args: Arguments from the tool call.

        Returns:
            The outputs from the plugin.
        """
        self._log_debug(
            f"Executing plugin [{plugin_node['id']}] in parent context with args: {args}"
        )

        node_def = self.nodes.get(plugin_node["type"])
        if not node_def:
            raise NodeError(
                message=f"Node type '{plugin_node['type']}' not found.",
                node_id=plugin_node["id"],
                node_type=plugin_node["type"],
            )

        config = node_def.get("config", {})

        # Check if this is a macro (needs special handling)
        if config.get("is_macro"):
            self._log_debug(
                f"Plugin [{plugin_node['id']}] is a macro, using _process_macro_node"
            )

            # For macros called as plugins, we need to temporarily add the args
            # to the cache so the macro can access them via input collection
            temp_cache_keys: list[tuple[str, str]] = []

            # Store args in cache as if they came from upstream nodes
            for input_name, value in args.items():
                temp_node_id = f"__plugin_arg_{plugin_node['id']}"
                self.cache.set(node_id=temp_node_id, port_name=input_name, value=value)
                temp_cache_keys.append((temp_node_id, input_name))

                # Also add a temporary link so input collection can find it
                temp_link = {
                    "from": {"node_id": temp_node_id, "port_name": input_name},
                    "to": {"node_id": plugin_node["id"], "port_name": input_name},
                }
                self.flow["links"].append(temp_link)

            try:
                # Execute the macro
                outputs = await self._process_macro_node(plugin_node, args, config)
                return outputs
            finally:
                # Always clean up temporary cache entries and links, even on error
                for temp_node_id, port_name in temp_cache_keys:
                    self.cache.delete(node_id=temp_node_id, port_name=port_name)
                self.flow["links"] = [
                    link
                    for link in self.flow["links"]
                    if not link["from"]["node_id"].startswith("__plugin_arg_")
                ]

        # For regular nodes and imports
        # Collect static inputs (from parent flow connections)
        static_inputs = self._collect_static_inputs(plugin_node)

        # Merge static inputs with LLM-provided args
        merged_inputs = {**static_inputs, **args}

        self._log_debug(f"Merged inputs for plugin [{plugin_node['id']}]: {merged_inputs}")

        # Execute the plugin node with merged inputs
        outputs = await self._process_node_with_args(plugin_node, merged_inputs)

        # Store outputs in parent cache for downstream propagation
        self._log_debug(f"Storing plugin outputs in parent cache: {outputs}")
        for key, value in outputs.items():
            self.cache.set(node_id=plugin_node["id"], port_name=key, value=value)

        # Propagate outputs downstream in parent context
        await self.propagate(plugin_node["id"])

        return outputs

    def _collect_static_inputs(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        Collect statically connected inputs for a plugin node.

        These are inputs connected via regular data links (not plugin links),
        which should be used alongside LLM-provided arguments.

        Args:
            node: The plugin node to collect inputs for.

        Returns:
            Dictionary of input name -> value for statically connected inputs.
        """
        config = self.nodes.get(node["type"], {}).get("config", {})
        static_inputs: dict[str, Any] = {}

        # Find all statically connected inputs (non-plugin links)
        static_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"] and link.get("type") != "plugin"
        ]

        for link in static_links:
            input_name = link["to"].get("port_name")
            if not input_name:
                continue

            input_def = next(
                (i for i in config.get("inputs", []) if i["name"] == input_name), None
            )
            if not input_def:
                continue

            value = self.cache.get(
                node_id=link["from"]["node_id"], port_name=link["from"]["port_name"]
            )

            if value is not None:
                if input_def.get("allow_multiple"):
                    if input_name not in static_inputs:
                        static_inputs[input_name] = []
                    # If value is a list and doesn't match the expected type,
                    # check if it's a list of the expected type and spread it in
                    item_type = input_def.get("type", "any")
                    if isinstance(value, list) and not type_check(value, item_type, self.custom_types):
                        all_valid = len(value) > 0 and all(
                            type_check(item, item_type, self.custom_types) for item in value
                        )
                        if all_valid:
                            static_inputs[input_name].extend(value)
                        # else silently skip invalid items
                    else:
                        static_inputs[input_name].append(value)
                else:
                    static_inputs[input_name] = value

        # Handle unconnected inputs with default values
        for input_def in config.get("inputs", []):
            input_name = input_def["name"]
            if input_name not in static_inputs and input_def.get("default") is not None:
                static_inputs[input_name] = input_def["default"]

        return static_inputs

    def _generate_tool_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        Generate a tool schema from a plugin node.

        Args:
            node: The plugin node to generate a schema for.

        Returns:
            A tool schema dict with name, description, and parameters.
        """
        from src.helpers import create_safe_tool_name, map_type_to_json_schema

        config = self.nodes.get(node["type"], {}).get("config", {})
        settings = node.get("settings", {})

        # Use node's custom display name if present
        name = node.get("display_name") or config.get("display_name") or node["type"]
        name = create_safe_tool_name(name)

        description = node.get("description") or config.get("description") or ""

        # Find which inputs are statically connected (not available to LLM)
        statically_connected_inputs: set[str] = set()
        for link in self.flow.get("links", []):
            if link["to"]["node_id"] == node["id"] and link.get("type") != "plugin":
                port_name = link["to"].get("port_name")
                if port_name:
                    statically_connected_inputs.add(port_name)

        # Build JSON Schema properties for each input NOT statically connected
        properties: dict[str, Any] = {}
        required: list[str] = []

        for input_def in config.get("inputs", []):
            input_name = input_def["name"]

            # Skip inputs that are statically connected
            if input_name in statically_connected_inputs:
                continue

            if config.get("is_import"):
                if input_def.get("is_data_input"):
                    properties[input_name] = {
                        "type": input_def.get("type", "object"),
                        "description": input_def.get("description", ""),
                    }
                elif input_def.get("is_chat_input"):
                    properties[input_name] = {
                        "type": "string",
                        "description": "A conversational chat message to send to this agent.",
                    }
                elif input_def.get("is_prompt_input"):
                    properties[input_name] = {
                        "type": "string",
                        "description": input_def.get("description", ""),
                    }
                if input_def.get("required"):
                    required.append(input_name)
            else:
                properties[input_name] = {
                    "type": map_type_to_json_schema(input_def.get("type")),
                    "description": input_def.get("description", ""),
                }
                if input_def.get("default") is not None:
                    properties[input_name]["default"] = input_def["default"]
                if input_def.get("required"):
                    required.append(input_name)

        return {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    async def _process_node_with_args(
        self, node: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a node with specific arguments (used for plugin execution).

        Args:
            node: The node to process.
            args: The merged arguments (static inputs + LLM args).

        Returns:
            The outputs from the node.
        """
        self._log_debug(f"Processing node [{node['id']}] with args: {args}")

        node_def = self.nodes.get(node["type"])
        if not node_def:
            raise NodeError(
                message=f"Node type '{node['type']}' not found.",
                node_id=node["id"],
                node_type=node["type"],
            )

        settings = node.get("settings", {})

        # Validate inputs
        config = node_def.get("config", {})
        validate_inputs(config, args, self.custom_types, debug=self.debug)

        # Execute using the core logic
        outputs = await self._execute_node_core(node, args, settings, node_def)

        self._log_debug(f"Process node with args outputs: {outputs}")
        return outputs

    async def _process_imported_chat_node(
        self, node: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process imported nodes with chat inputs, maintaining conversation state.

        This handles multi-turn conversations by:
        1. Finding chat input nodes in the imported flow
        2. Converting string arguments to message arrays with history
        3. Processing the node
        4. Updating conversation history with responses

        Args:
            node: The imported node to process.
            args: Arguments from the LLM tool call.

        Returns:
            The outputs from the node.
        """
        self._log_debug(f"Processing imported chat node [{node['id']}] with args: {args}")

        node_def = self.nodes.get(node["type"])
        if not node_def:
            raise NodeError(
                message=f"Node type '{node['type']}' not found.",
                node_id=node["id"],
                node_type=node["type"],
            )

        config = node_def.get("config", {})
        if not config.get("is_import"):
            raise NodeError(
                message=f"Node {node['id']} is not an imported node",
                node_id=node["id"],
                node_type=node["type"],
            )

        # Find the imported flow definition to get the actual input-chat nodes
        import_def = config.get("importDefinition", {})

        # Transform string arguments to message arrays for each chat input
        transformed_args = {**args}
        inputs = config.get("inputs", [])

        for chat_input in inputs:
            if not chat_input.get("is_chat_input"):
                continue

            input_value = args.get(chat_input["name"])
            if not isinstance(input_value, str):
                continue

            # The input's name IS the input-chat node's settings.key, so use it
            # directly. The previous lookup compared the key against node ids,
            # always missed, and fell back to "chat" — collapsing every chat
            # stream into one and ignoring custom keys.
            chat_key = chat_input["name"]

            # Create conversation key: nodeId + chatKey for this specific chat stream
            conversation_key = f"{node['id']}_{chat_key}"

            if conversation_key not in self._conversation_state:
                self._conversation_state[conversation_key] = []

            # Add the new user message to this chat stream's history
            self._conversation_state[conversation_key].append({
                "role": "user",
                "content": input_value,
            })

            # Pass the full conversation history for this chat stream
            transformed_args[chat_input["name"]] = list(
                self._conversation_state[conversation_key]
            )

            self._log_debug(
                f"Updated conversation for {conversation_key}: "
                f"{self._conversation_state[conversation_key]}"
            )

        # Process the imported node with the full conversation context
        outputs = await self._process_node_with_args(node, transformed_args)

        # Handle responses from output-chat nodes and append to appropriate streams
        output_chat_nodes = [
            n for n in import_def.get("nodes", [])
            if n.get("type") == "output-chat"
        ]

        for output_chat_node in output_chat_nodes:
            chat_key = output_chat_node.get("settings", {}).get("key", "chat")
            conversation_key = f"{node['id']}_{chat_key}"

            # The import's process emits the response under the output-chat's
            # key, not the bare node id. Read by key (fall back to id for safety)
            # so the assistant's replies actually get appended to the conversation.
            chat_output = outputs.get(chat_key, outputs.get(output_chat_node["id"]))

            self._log_debug(
                f"Looking for output from node {output_chat_node['id']} "
                f"with chat key {chat_key}: {chat_output}"
            )

            if chat_output and isinstance(chat_output, list):
                if conversation_key not in self._conversation_state:
                    self._conversation_state[conversation_key] = []

                # The chat output contains new response messages to append
                if len(chat_output) > 0:
                    self._conversation_state[conversation_key].extend(chat_output)
                    self._log_debug(
                        f"Appended {len(chat_output)} new messages to "
                        f"conversation {conversation_key}: {chat_output}"
                    )
            else:
                self._log_debug(
                    f"No chat output found for node {output_chat_node['id']}, "
                    f"available outputs: {list(outputs.keys())}"
                )

        return outputs

    def reset_conversation_state(
        self,
        node_id: str | None = None,
        chat_key: str | None = None,
    ) -> None:
        """
        Reset conversation state for specific chat streams or all conversations.

        Args:
            node_id: Optional node ID to reset conversations for.
            chat_key: Optional chat key to reset specific chat stream.
        """
        if node_id and chat_key:
            conversation_key = f"{node_id}_{chat_key}"
            if conversation_key in self._conversation_state:
                del self._conversation_state[conversation_key]
            self._log_debug(
                f"Reset conversation state for node {node_id}, chat key {chat_key}"
            )
        elif node_id:
            # Reset all chat streams for this node
            keys_to_delete = [
                key for key in self._conversation_state
                if key.startswith(f"{node_id}_")
            ]
            for key in keys_to_delete:
                del self._conversation_state[key]
            self._log_debug(f"Reset all conversation states for node {node_id}")
        else:
            self._conversation_state = {}
            self._log_debug("Reset all conversation states")

    async def wait_for_node_completion(self) -> None:
        """
        Wait for any running node to complete.

        This method uses event-based signaling instead of polling,
        enabling efficient async coordination for concurrency management.

        If no nodes are running, returns immediately.
        """
        if len(self.running_nodes) == 0:
            return

        # Create a future that will be resolved when a node completes
        loop = asyncio.get_event_loop()
        future: asyncio.Future[None] = loop.create_future()
        self._node_completion_resolvers.append(future)

        # Wait for the future to be resolved
        await future

    def _signal_node_completion(self) -> None:
        """
        Signal that a node has completed execution.

        This resolves the first pending future in the resolver queue,
        allowing one waiter to continue.
        """
        if self._node_completion_resolvers:
            future = self._node_completion_resolvers.pop(0)
            if not future.done():
                future.set_result(None)

    async def _call_llm_with_tools(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        tool_schemas: list[dict[str, Any]],
        tool_call_message: dict[str, Any] | None,
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Call the LLM with tools injected into inputs.

        Args:
            node: The LLM node.
            inputs: The inputs for the LLM.
            tool_schemas: List of tool schemas to inject.
            tool_call_message: Previous tool call message (if continuing).
            tool_results: Results from previous tool calls.

        Returns:
            The LLM outputs.
        """
        node_def = self.nodes.get(node["type"])
        if not node_def:
            raise NodeError(
                message=f"Node type '{node['type']}' not found.",
                node_id=node["id"],
                node_type=node["type"],
            )

        # Copy inputs and merge plugin/manual toolSchemas with any tools already in inputs
        # Deduplicate by tool name since tools from the "tools" input port are collected
        # both during normal input collection and during tool schema gathering
        llm_inputs = {**inputs}
        input_tools = llm_inputs.get("tools", []) if isinstance(llm_inputs.get("tools"), list) else []
        seen_tool_names: set[str] = set()
        llm_inputs["tools"] = []
        for tool in [*tool_schemas, *input_tools]:
            name = tool.get("name") if isinstance(tool, dict) else None
            if name and name not in seen_tool_names:
                seen_tool_names.add(name)
                llm_inputs["tools"].append(tool)

        # If this is a tool call response, append to messages
        if tool_call_message and tool_results and isinstance(llm_inputs.get("messages"), list):
            llm_inputs["messages"] = [*llm_inputs["messages"], tool_call_message]

            for tool_result in tool_results:
                result_content = tool_result["result"]
                if not isinstance(result_content, str):
                    result_content = json.dumps(result_content)

                llm_inputs["messages"].append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "name": tool_result["name"],
                    "content": result_content,
                })

        # Execute using the shared core logic
        outputs = await self._execute_node_core(
            node, llm_inputs, node.get("settings", {}), node_def
        )

        return outputs

    async def _process_llm_node(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        node_def: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process an LLM node with plugin/tool support.

        This implements the tool-calling loop:
        1. Gather plugin/tool schemas
        2. Call LLM with tools
        3. If LLM requests tool calls, execute them
        4. Continue until LLM is done or max calls reached

        Args:
            node: The LLM node to process.
            inputs: The collected inputs for the node.
            node_def: The node definition.

        Returns:
            The final outputs from the LLM.
        """
        self._log_debug(f"Processing LLM node [{node['id']}] with plugin support")

        config = node_def.get("config", {})

        # Validate inputs
        validate_inputs(config, inputs, self.custom_types, debug=self.debug)

        # 1. Gather plugin/tool schemas and runners
        tool_schemas: list[dict[str, Any]] = []
        tool_runners: dict[str, Any] = {}  # tool_name -> async runner function
        tool_node_map: dict[str, dict[str, Any]] = {}  # tool_name -> node info

        # Check for tools provided from config (parent context or developer-provided)
        if self.config.get("tools") and isinstance(self.config["tools"], dict):
            for tool_name, tool_def in self.config["tools"].items():
                if tool_def.get("schema"):
                    tool_schemas.append(tool_def["schema"])
                if tool_def.get("process"):
                    tool_runners[tool_name] = tool_def["process"]

        # Discover local plugins
        plugin_node_ids = self.llm_plugins.get(node["id"], [])
        self._log_debug(f"Found {len(plugin_node_ids)} plugins for LLM node [{node['id']}]")

        for plugin_node_id in plugin_node_ids:
            plugin_node = next(
                (n for n in self.flow["nodes"] if n["id"] == plugin_node_id), None
            )
            if not plugin_node:
                continue

            if self._is_local_node_plugin(plugin_node):
                schema = self._generate_tool_schema(plugin_node)
                tool_schemas.append(schema)
                tool_node_map[schema["name"]] = {"node": plugin_node, "type": "plugin"}

                plugin_node_def = self.nodes.get(plugin_node["type"], {})
                plugin_config = plugin_node_def.get("config", {})

                # Create runner for this plugin
                async def create_runner(pn: dict, pn_def: dict, pc: dict) -> Any:
                    async def runner(args: dict[str, Any]) -> dict[str, Any]:
                        # Merge static inputs with LLM args
                        static_inputs = self._collect_static_inputs(pn)
                        merged_inputs = {**static_inputs, **args}
                        self._log_debug(f"Executing plugin [{pn['id']}] with merged inputs: {merged_inputs}")

                        # Check if this is a macro
                        if pc.get("is_macro"):
                            # For macros, inject args into cache and process
                            temp_cache_keys = []
                            for input_name, value in merged_inputs.items():
                                temp_node_id = f"__plugin_arg_{pn['id']}"
                                self.cache.set(node_id=temp_node_id, port_name=input_name, value=value)
                                temp_cache_keys.append((temp_node_id, input_name))
                                # Add temporary link
                                temp_link = {
                                    "from": {"node_id": temp_node_id, "port_name": input_name},
                                    "to": {"node_id": pn["id"], "port_name": input_name},
                                }
                                self.flow["links"].append(temp_link)

                            try:
                                outputs = await self._process_macro_node(pn, merged_inputs, pc)
                                return outputs
                            finally:
                                # Cleanup temp cache and links
                                for temp_node_id, port_name in temp_cache_keys:
                                    self.cache.delete(node_id=temp_node_id, port_name=port_name)
                                self.flow["links"] = [
                                    l for l in self.flow["links"]
                                    if not l["from"]["node_id"].startswith("__plugin_arg_")
                                ]

                        # Check if this is an imported node with chat inputs
                        elif pc.get("is_import") and any(
                            inp.get("is_chat_input") for inp in pc.get("inputs", [])
                        ):
                            # Use conversation state-aware processing
                            outputs = await self._process_imported_chat_node(pn, merged_inputs)

                            # Store outputs in cache for downstream propagation
                            for key, value in outputs.items():
                                self.cache.set(node_id=pn["id"], port_name=key, value=value)

                            # Propagate downstream
                            await self.propagate(pn["id"])

                            return outputs

                        else:
                            # Regular plugin node
                            outputs = await self._process_node_with_args(pn, merged_inputs)

                            # Store outputs in cache for downstream propagation
                            for key, value in outputs.items():
                                self.cache.set(node_id=pn["id"], port_name=key, value=value)

                            # Propagate downstream
                            await self.propagate(pn["id"])

                            return outputs

                    return runner

                # Create and store the runner
                tool_runners[schema["name"]] = await create_runner(
                    plugin_node, plugin_node_def, plugin_config
                )

            elif is_remote_mcp_tool(plugin_node):
                # Resolve named MCP integration from config.keys.mcp
                integration_name = plugin_node.get("settings", {}).get("mcp_integration")
                if not integration_name:
                    self._log_debug(f"MCP plugin node [{plugin_node['id']}] has no mcp_integration setting")
                    continue
                mcp_config = self.config.get("keys", {}).get("mcp", {}).get(integration_name)
                if not mcp_config or not mcp_config.get("url"):
                    self._log_debug(f"MCP integration \"{integration_name}\" not found in config.keys.mcp")
                    continue
                mcp_url = mcp_config["url"]
                mcp_token = mcp_config.get("token")

                try:
                    mcp_schemas = await fetch_mcp_tools(mcp_url, mcp_token)
                    for mcp_schema in mcp_schemas:
                        tool_schemas.append(mcp_schema)
                        tool_node_map[mcp_schema["name"]] = {
                            "node": plugin_node,
                            "type": "mcp",
                        }

                        # Create runner for this MCP tool
                        async def create_mcp_runner(
                            tool_name: str, url: str, token: Optional[str]
                        ) -> Any:
                            async def runner(args: dict[str, Any]) -> Any:
                                self._log_debug(
                                    f"Calling MCP tool '{tool_name}' with args: {args}"
                                )
                                mcp_args = {**args, "name": tool_name}
                                result = await call_mcp_tool(mcp_args, url=url, token=token)
                                return result

                            return runner

                        tool_runners[mcp_schema["name"]] = await create_mcp_runner(
                            mcp_schema["name"], mcp_url, mcp_token
                        )

                    self._log_debug(f"Loaded {len(mcp_schemas)} MCP tools from \"{integration_name}\"")
                except Exception as e:
                    self._log_debug(f"Failed to fetch MCP tools from \"{integration_name}\" ({mcp_url}): {e}")
                    # Continue with other plugins even if MCP fails

        # Also gather tool schemas connected to the LLM's 'tools' input port
        tool_input_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"] and link["to"].get("port_name") == "tools"
        ]
        for link in tool_input_links:
            cached_value = self.cache.get(
                node_id=link["from"]["node_id"], port_name=link["from"]["port_name"]
            )
            if not cached_value:
                continue
            # Normalize to a list — could be a single tool or a list of tools
            schemas = cached_value if isinstance(cached_value, list) else [cached_value]
            for tool_schema in schemas:
                if not isinstance(tool_schema, dict) or not tool_schema.get("name"):
                    continue
                # Only add if not already in config tools
                config_tool = self.config.get("tools", {}).get(tool_schema.get("name"))
                if not config_tool or not config_tool.get("schema"):
                    tool_schemas.append(tool_schema)

        self._log_debug(f"Total tools available: {len(tool_schemas)}")
        if tool_schemas:
            self._log_debug(f"Tool names: {[t['name'] for t in tool_schemas]}")

        # Extract internal tool names (tools handled by engine plugins, not manual/external tools)
        # This is used by LLM nodes to filter the conversation output to only include
        # messages related to internally-handled tools
        internal_tool_names = [
            name for name, info in tool_node_map.items()
            if info.get("type") in ("plugin", "mcp")
        ]
        self.config["internal_tool_names"] = internal_tool_names
        self._log_debug(f"Internal tool names for LLM node [{node['id']}]: {internal_tool_names}")

        # 2. Tool calling loop
        llm_result: dict[str, Any] = {}
        tool_results: list[dict[str, Any]] = []
        tool_call_message: dict[str, Any] | None = None
        tool_call_count = 0

        # Normalize string/object messages to array format before accumulation
        messages_val = inputs.get("messages")
        if isinstance(messages_val, str):
            inputs["messages"] = [{"role": "user", "content": messages_val}]
        elif isinstance(messages_val, dict):
            inputs["messages"] = [messages_val]

        # Track accumulated messages
        accumulated_messages = list(inputs.get("messages", [])) if isinstance(inputs.get("messages"), list) else []

        while True:
            # Create inputs with accumulated messages
            round_inputs = {**inputs, "messages": accumulated_messages}

            llm_result = await self._call_llm_with_tools(
                node, round_inputs, tool_schemas, tool_call_message, tool_results
            )

            # After LLM call, update accumulated messages if there were tool calls
            if tool_call_message and tool_results:
                accumulated_messages = [*accumulated_messages, tool_call_message]
                for tr in tool_results:
                    result_content = tr["result"]
                    if not isinstance(result_content, str):
                        result_content = json.dumps(result_content)
                    accumulated_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "name": tr["name"],
                        "content": result_content,
                    })

            tool_results = []
            tool_call_message = None

            # Check if LLM wants to call tools
            if llm_result.get("tool_calls") and isinstance(llm_result["tool_calls"], list) and len(llm_result["tool_calls"]) > 0:
                self._log_debug(f"LLM requested {len(llm_result['tool_calls'])} tool calls")

                for tool_call in llm_result["tool_calls"]:
                    if tool_call.get("type") == "function" and tool_call.get("function"):
                        tool_name = tool_call["function"]["name"]
                        self._log_debug(f"Processing tool call: {tool_name}")

                        if tool_name in tool_runners:
                            tool_node_info = tool_node_map.get(tool_name)

                            # Parse arguments
                            try:
                                tool_arguments = tool_call["function"]["arguments"]
                                if isinstance(tool_arguments, str):
                                    tool_arguments = json.loads(tool_arguments)
                            except json.JSONDecodeError as e:
                                self._log_debug(f"Failed to parse tool arguments: {e}")
                                tool_results.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "name": tool_name,
                                    "result": {"error": True, "message": f"Invalid arguments: {e}"},
                                })
                                continue

                            # Execute the tool
                            # Note: _execute_node_core already creates timeline entries
                            try:
                                self._log_debug(f"Executing tool {tool_name} with args: {tool_arguments}")
                                tool_result = await tool_runners[tool_name](tool_arguments)

                                tool_results.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "name": tool_name,
                                    "result": tool_result,
                                })

                            except Exception as e:
                                self._log_debug(f"Tool execution failed: {e}")
                                # Note: _execute_node_core already creates error timeline entries

                                tool_results.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "name": tool_name,
                                    "result": {"error": True, "message": str(e)},
                                })
                        else:
                            self._log_debug(f"No runner found for tool: {tool_name}")
                            tool_results.append({
                                "tool_call_id": tool_call.get("id"),
                                "name": tool_name,
                                "result": {"error": True, "message": f"Tool '{tool_name}' is not available"},
                            })

                # Prepare tool call message for next round
                tool_call_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": llm_result["tool_calls"],
                }
                tool_call_count += 1

                # Check if we should continue
                if tool_call_count >= self.max_plugin_calls:
                    self._log_debug(f"Reached max plugin calls ({self.max_plugin_calls})")
                    break
            else:
                # No more tool calls, exit loop
                break

        # Clean up internal_tool_names from config
        self.config.pop("internal_tool_names", None)

        self._log_debug(f"LLM node [{node['id']}] processing completed")
        return llm_result

    def _collect_node_inputs(
        self,
        node: dict[str, Any],
        node_def: dict[str, Any],
    ) -> dict[str, Any]:
        """Collect inputs for a node from the cache."""
        inputs: dict[str, Any] = {}
        config = node_def.get("config", {})
        input_defs = config.get("inputs", [])

        # Get links to this node (filter out plugin links - they don't have port_name)
        node_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"]
            and link.get("type") != "plugin"  # Plugin links don't have port_name
        ]

        # Track connected inputs
        connected_inputs = {link["to"].get("port_name") for link in node_links if link["to"].get("port_name")}

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
                    item_type = input_def.get("type", "any")
                    # If value is a list and doesn't match the expected type,
                    # check if it's a list of the expected type and spread it in
                    if isinstance(value, list) and not type_check(value, item_type, self.custom_types):
                        all_valid = len(value) > 0 and all(
                            type_check(item, item_type, self.custom_types) for item in value
                        )
                        if all_valid:
                            inputs[input_name].extend(value)
                    elif type_check(value, item_type, self.custom_types):
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

    async def _race_abort(self, coro: Any) -> Any:
        """Race a node's process coroutine against the flow's abort signal.

        On abort (flow timeout, or an ancestor engine aborting), the inner task
        is cancelled — which propagates CancelledError into any in-flight
        httpx/SDK call, actually stopping it — and a TimeoutError is raised so
        the execution loop doesn't park on a hung node. No-op when there's no
        signal, so callers outside run() behave exactly as before.
        """
        signal = self.config.get("signal")
        if signal is None:
            return await coro
        task = asyncio.ensure_future(coro)
        waiter = asyncio.ensure_future(signal.wait())
        try:
            await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
            if task.done():
                return task.result()
            # Aborted before the node finished — cancel the in-flight work.
            task.cancel()
            try:
                await task
            except BaseException:
                pass
            raise TimeoutError("Flow execution timed out")
        finally:
            if not waiter.done():
                waiter.cancel()
            # If _race_abort itself was cancelled externally before handling the
            # abort, cancel the node task too — asyncio.wait does not cancel its
            # awaited tasks, so it would otherwise leak (and keep its httpx call).
            if not task.done():
                task.cancel()

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

            outputs = await self._race_abort(
                process_func(
                    inputs=inputs,
                    settings=settings,
                    config=self.config,
                    node_config=config,
                )
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

            # Call on_node_error callback
            if self.config.get("on_node_error"):
                await self._call_callback(
                    self.config["on_node_error"],
                    {
                        "node_id": node["id"],
                        "node_type": node["type"],
                        "timestamp": int(end_time * 1000),
                        "error": str(e),
                        "inputs": inputs,
                        "settings": settings,
                        "duration_ms": timeline_entry.duration_ms,
                    },
                )

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

        # Find downstream nodes (skip plugin links - they don't have port_name)
        downstream_links = [
            link
            for link in self.flow.get("links", [])
            if link["from"]["node_id"] == current_node_id
            and link.get("type") != "plugin"  # Plugin links don't have port_name
            and link["from"].get("port_name")  # Must have port_name
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

        # Get links to this node (filter out plugin links - they don't affect readiness)
        node_links = [
            link
            for link in self.flow.get("links", [])
            if link["to"]["node_id"] == node["id"]
            and link.get("type") != "plugin"  # Plugin links don't affect readiness
        ]

        # Group by input name
        links_by_input: dict[str, list[dict[str, Any]]] = {}
        for link in node_links:
            port_name = link["to"].get("port_name")
            if not port_name:
                continue  # Skip links without port_name (shouldn't happen for data links)
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

        # Preemptive cancellation: an asyncio.Event exposed as config["signal"]
        # and set when the flow times out. _race_abort() then cancels the
        # in-flight node task (cancellation propagates into httpx/SDK calls and
        # actually stops them) instead of the launch loop parking on a hung node.
        self._abort_event = asyncio.Event()
        self._abort_link_task = None
        # Cascade: if an ancestor engine passed its signal in (macro / imported
        # sub-engine via {**config}), abort when it aborts. Use the construction-
        # time inherited signal, not config["signal"] (a prior run() may have
        # overwritten it with that run's own, now-stale, Event).
        inherited_signal = self._inherited_signal
        if inherited_signal is not None:
            if inherited_signal.is_set():
                self._abort_event.set()
            else:
                async def _link_abort() -> None:
                    await inherited_signal.wait()
                    if self._abort_event:
                        self._abort_event.set()

                self._abort_link_task = asyncio.create_task(_link_abort())
        # Expose our signal to node processes and sub-engines.
        self.config["signal"] = self._abort_event

        if self.error_manager:
            self.error_manager.update_execution_context(
                {"timeout": timeout, "start_time": time.time()}
            )

        # Set timeout
        abort_event = self._abort_event

        async def timeout_handler() -> None:
            await asyncio.sleep(timeout / 1000)
            self.has_timed_out = True
            abort_event.set()
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
                        # Normalize string/object to message array
                        if isinstance(value, str):
                            value = [{"role": "user", "content": value}]
                        elif isinstance(value, dict):
                            value = [value]
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

                    # _launch_node awaits serially, so running_nodes is usually
                    # empty by here — surface any error/timeout now, otherwise the
                    # loop can drain and return having swallowed it (e.g. a node
                    # aborted by the flow timeout via _race_abort).
                    if self.last_error:
                        error = self.last_error
                        self.last_error = None
                        raise error
                    if self.has_timed_out:
                        raise TimeoutError("Flow execution timed out.")

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
            if self._abort_link_task:
                self._abort_link_task.cancel()
            # Restore the inherited signal so a reused engine doesn't treat this
            # run's (possibly set) Event as an ancestor on the next run().
            self.config["signal"] = self._inherited_signal

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
            self._signal_node_completion()
            await self.propagate(node["id"])

        except Exception as e:
            self.running_nodes.discard(node["id"])
            self._signal_node_completion()
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

    def track_knowledge_file(self, file_path: str) -> None:
        """
        Track a knowledge base file for cleanup.

        Args:
            file_path: Path to the knowledge base file.
        """
        if file_path and "knowledge_" in file_path:
            self._knowledge_files_to_cleanup.add(file_path)
            self._log_debug(f"Tracking knowledge file for cleanup: {file_path}")

    def _track_knowledge_files(self) -> None:
        """Track all knowledge base files that need cleanup."""
        # Track main flow's knowledge base file
        if self.flow.get("knowledgeDbPath"):
            self.track_knowledge_file(self.flow["knowledgeDbPath"])

        # Track import knowledge base files
        imports = self.flow.get("imports", [])
        if imports and isinstance(imports, list):
            for import_def in imports:
                if import_def.get("knowledgeDbPath"):
                    self.track_knowledge_file(import_def["knowledgeDbPath"])

    async def _cleanup_temp_knowledge_files(self) -> None:
        """Clean up temporary knowledge base files for this specific engine instance."""
        try:
            temp_dir = Path.cwd() / ".temp"
            if not temp_dir.exists():
                return  # No temp directory exists

            # Clean up tracked knowledge files first
            for file_path in self._knowledge_files_to_cleanup:
                try:
                    path = Path(file_path)
                    if path.exists():
                        path.unlink()
                        self._log_debug(f"Cleaned up tracked knowledge file: {file_path}")

                    # Also clean up any lock files
                    lock_path = Path(f"{file_path}.lock")
                    if lock_path.exists():
                        lock_path.unlink()
                        self._log_debug(f"Cleaned up lock file: {lock_path}")

                except Exception as e:
                    logger.warning(
                        f"Failed to cleanup tracked knowledge file {file_path}: {e}"
                    )

            # Get the flow ID to identify our specific temporary files
            flow_id = self.flow.get("id") or self.flow.get("metadata", {}).get("id")
            if not flow_id:
                self._log_debug(
                    "No flow ID found, skipping additional knowledge file cleanup"
                )
                return

            # Look for any remaining knowledge files that match our flow ID pattern
            try:
                files = list(temp_dir.iterdir())
                knowledge_files = [
                    f for f in files
                    if f.name == f"knowledge_{flow_id}.db"
                ]

                for file in knowledge_files:
                    try:
                        file.unlink()
                        self._log_debug(
                            f"Cleaned up additional temporary knowledge file: {file}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to cleanup additional temporary knowledge file {file}: {e}"
                        )

                    # Also clean up any lock files
                    lock_path = Path(f"{file}.lock")
                    if lock_path.exists():
                        try:
                            lock_path.unlink()
                            self._log_debug(f"Cleaned up lock file: {lock_path}")
                        except Exception:
                            pass  # Ignore lock file cleanup errors

                # Also clean up any knowledge files that are older than 1 hour (safety)
                one_hour_ago = time.time() - (60 * 60)
                all_knowledge_files = [
                    f for f in files
                    if f.name.startswith("knowledge_") and f.name.endswith(".db")
                ]

                for file in all_knowledge_files:
                    try:
                        if file.stat().st_mtime < one_hour_ago:
                            file.unlink()
                            self._log_debug(
                                f"Cleaned up old temporary knowledge file: {file}"
                            )
                    except Exception:
                        pass  # Ignore errors for old file cleanup

                # If temp directory is now empty, remove it
                try:
                    remaining_files = list(temp_dir.iterdir())
                    if len(remaining_files) == 0:
                        temp_dir.rmdir()
                        self._log_debug("Removed empty temporary directory")
                except Exception:
                    pass  # Ignore errors for directory cleanup

            except Exception:
                pass  # Ignore errors reading temp directory

        except Exception as e:
            logger.warning(f"Error during temporary knowledge file cleanup: {e}")
            # Don't throw - cleanup should be best effort

    async def cleanup(self) -> None:
        """Clean up resources including knowledge databases and temporary files."""
        self._log_debug("Starting cleanup...")

        try:
            # Clean up integrations
            integrations = self.config.get("integrations", {})

            if "knowledge_base" in integrations:
                kb = integrations["knowledge_base"]
                if hasattr(kb, "disconnect"):
                    await kb.disconnect()

            # Clean up any remaining temporary knowledge base files
            await self._cleanup_temp_knowledge_files()

            # Clear cache
            self.cache.clear()
            self.timeline.clear()

            self._log_debug("Cleanup completed")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
