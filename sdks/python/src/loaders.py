"""
Loading utilities for the zv1 engine.

This module provides:
- Node loading from filesystem
- Flow loading (JSON and .zv1 files)
- Integration loading
- Import handling
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.helpers import get_nodes_dir
from src.types import convert_import_to_node_type

if TYPE_CHECKING:
    from src.types import TypeInfo

logger = logging.getLogger(__name__)


# Type for node process functions
ProcessFunction = Callable[..., Any]


async def load_nodes(
    flow: dict[str, Any],
    nodes_dir: Path | None = None,
    debug: bool = False,
) -> dict[str, dict[str, Any]]:
    """
    Load node configurations and process functions.

    Args:
        flow: The flow definition (to find which node types are used).
        nodes_dir: Path to nodes directory. Defaults to SDK nodes dir.
        debug: Whether to log debug messages.

    Returns:
        Dict mapping node types to their definitions (config + process).
    """
    if nodes_dir is None:
        nodes_dir = get_nodes_dir()

    # Collect all node types used in the flow (including nested imports)
    node_types: set[str] = set()

    def find_node_types(f: dict[str, Any]) -> None:
        for node in f.get("nodes", []):
            node_types.add(node["type"])
        for imp in f.get("imports", []):
            find_node_types(imp)

    find_node_types(flow)

    nodes: dict[str, dict[str, Any]] = {}

    # Load regular nodes from filesystem
    async def load_node(node_type: str) -> None:
        # Skip imported node types
        if node_type.startswith("imported-"):
            return

        node_path = nodes_dir / node_type
        config_path = node_path / f"{node_type}.config.json"
        process_path = node_path / f"{node_type}.process.py"

        if not config_path.exists():
            if debug:
                logger.warning(f"Missing config file for node {node_type}: {config_path}")
            return

        try:
            # Load config
            with open(config_path) as f:
                config = json.load(f)

            # Check if this is a macro node (no process file needed)
            if config.get("is_macro"):
                nodes[node_type] = {"config": config, "process": None}
                return

            # Load process function
            if process_path.exists():
                process_func = await _load_process_function(process_path)
                nodes[node_type] = {"config": config, "process": process_func}
            else:
                if debug:
                    logger.warning(
                        f"Missing process file for regular node {node_type}: {process_path}"
                    )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config for node {node_type}: {e}")
        except Exception as e:
            logger.error(f"Failed to load node {node_type}: {e}")

    # Load all nodes concurrently
    await asyncio.gather(*[load_node(node_type) for node_type in node_types])

    # Load imports as node types
    for import_def in flow.get("imports", []):
        node_type = convert_import_to_node_type(import_def)
        import_id = import_def.get("id", "")
        nodes[import_id] = node_type
        nodes[f"imported-{import_id}"] = node_type

    if debug:
        logger.debug(f"Loaded {len(nodes)} node types")

    return nodes


async def _load_process_function(process_path: Path) -> ProcessFunction:
    """
    Load a process function from a Python file.

    Args:
        process_path: Path to the .process.py file.

    Returns:
        The process function.
    """
    spec = importlib.util.spec_from_file_location(
        f"node_process_{process_path.stem}",
        process_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {process_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The process function should be named 'process'
    if hasattr(module, "process"):
        return module.process

    raise ImportError(f"No 'process' function found in {process_path}")


async def load_integrations(
    config: dict[str, Any],
    flow: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """
    Load integrations based on configuration.

    Args:
        config: Engine configuration containing keys and integration settings.
        flow: Optional flow that may contain knowledge database path.
        debug: Whether to log debug messages.

    Returns:
        Dict of initialized integrations.
    """
    integrations: dict[str, Any] = {}
    keys = config.get("keys", {})

    # Load OpenRouter integration if API key is provided
    if keys.get("openrouter"):
        try:
            from src.integrations.openrouter import OpenRouterIntegration

            integrations["openrouter"] = OpenRouterIntegration(
                api_key=keys["openrouter"],
                base_url=config.get("openrouter_base_url", "https://openrouter.ai/api/v1"),
                referer="https://workbench.zerowidth.ai",
                title="Workbench by ZeroWidth",
            )
            if debug:
                logger.debug("Loaded OpenRouter integration")
        except ImportError as e:
            logger.warning(f"Failed to load OpenRouter integration: {e}")

    # Load other basic integrations
    basic_integrations = ["firecrawl", "newsdata_io", "openai", "google_custom_search", "airtable", "notion", "sendgrid", "slack", "supabase", "pinecone", "twilio", "github", "linear", "stripe", "resend", "jira", "confluence"]

    for integration_name in basic_integrations:
        key_value = keys.get(integration_name)
        # Skip if no key, or if it's a dict with empty/None values
        if not key_value:
            continue
        if isinstance(key_value, dict) and not any(key_value.values()):
            continue

        try:
            # Dynamic import of integration module
            module = importlib.import_module(
                f"src.integrations.{integration_name}"
            )
            integration_class = getattr(
                module, f"{_to_class_name(integration_name)}Integration"
            )
            integrations[integration_name] = integration_class(key_value)
            if debug:
                logger.debug(f"Loaded {integration_name} integration")
        except (ImportError, AttributeError, ValueError) as e:
            logger.warning(f"Failed to load {integration_name} integration: {e}")

    # Load HubSpot integration (OAuth-based)
    if keys.get("hubspot"):
        try:
            from src.integrations.hubspot import HubSpotIntegration

            integrations["hubspot"] = HubSpotIntegration(keys["hubspot"])
            if debug:
                logger.debug("Loaded HubSpot integration")
        except ImportError as e:
            logger.warning(f"Failed to load HubSpot integration: {e}")

    # Load knowledge base integration if configured
    knowledge_config = config.get("knowledge_base", {})
    knowledge_type = knowledge_config.get("type", "sqlite")

    if flow and flow.get("knowledge_db_path") or knowledge_config.get("enabled") is not False:
        try:
            if knowledge_type == "sqlite":
                from src.integrations.sqlite import SQLiteIntegration

                db_path = flow.get("knowledge_db_path") if flow else None
                if db_path:
                    integrations["knowledge_base"] = SQLiteIntegration(
                        db_path,
                        timeout=config.get("sqlite_timeout", 5000),
                    )
                    integrations["sqlite"] = integrations["knowledge_base"]
                    if debug:
                        logger.debug("Loaded SQLite knowledge base integration")
        except ImportError as e:
            logger.warning(f"Failed to load knowledge base integration: {e}")

    # Set engine config reference on all integration instances
    # This allows integrations to emit on_api_call events without signature changes
    for name, instance in integrations.items():
        if not name.startswith("_") and hasattr(instance, "__dict__"):
            instance._engine_config = config

    return integrations


_CLASS_NAME_OVERRIDES = {
    "newsdata_io": "NewsData",
    "openai": "OpenAI",
}


def _to_class_name(snake_case: str) -> str:
    """Convert snake_case to PascalCase for class names."""
    if snake_case in _CLASS_NAME_OVERRIDES:
        return _CLASS_NAME_OVERRIDES[snake_case]
    return "".join(word.capitalize() for word in snake_case.split("_"))


async def detect_and_load_flow(
    input_data: str | dict[str, Any] | bytes,
) -> dict[str, Any]:
    """
    Detect the input format and load accordingly.

    Supports:
    - Legacy JSON files
    - New .zv1 files
    - Raw ZIP data in memory
    - Flow objects (passed through)

    Args:
        input_data: File path (str), flow object (dict), or ZIP data (bytes).

    Returns:
        Unified flow object ready for engine initialization.

    Raises:
        ValueError: If input format is unsupported.
        FileNotFoundError: If file doesn't exist.
    """
    # If input is already a dict, it's either a legacy flow or already processed
    if isinstance(input_data, dict):
        # Check if it has imports array - may need conversion
        if isinstance(input_data.get("imports"), list):
            return input_data

        # Legacy flow without imports - return as-is
        return input_data

    # If input is bytes, treat as raw ZIP data (.zv1 file in memory)
    if isinstance(input_data, bytes):
        return await load_flow_from_buffer(input_data)

    # Input is a string - treat as file path
    if isinstance(input_data, str):
        file_path = Path(input_data).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"Flow file not found: {file_path}")

        # .zwf is the current extension; .zv1 is the legacy name for the
        # identical zip format — still accepted.
        if file_path.suffix in (".zwf", ".zv1"):
            return await load_flow_archive(file_path)
        elif file_path.suffix == ".json":
            with open(file_path) as f:
                flow_data = json.load(f)

            # Convert legacy imports if present
            if isinstance(flow_data.get("imports"), list):
                flow_data["imports"] = convert_legacy_imports(flow_data["imports"])

            return flow_data
        else:
            raise ValueError(
                f"Unsupported file format. Expected .zwf, .zv1, or .json, got: {file_path.suffix}"
            )

    raise ValueError(
        "Invalid input type. Expected file path (str), flow object (dict), "
        "or ZIP data (bytes)."
    )


async def load_flow_archive(file_path: Path) -> dict[str, Any]:
    """
    Load a .zv1 file and extract its contents.

    .zv1 files are ZIP archives containing orchestration.json and
    optional imports folder.

    Args:
        file_path: Path to the .zv1 file.

    Returns:
        Extracted flow object.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file is invalid.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Zv1 file not found: {file_path}")

    if file_path.suffix not in (".zwf", ".zv1"):
        raise ValueError(f"Invalid file extension. Expected .zwf or .zv1, got: {file_path.suffix}")

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            return await _parse_zv1_zip(zf)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file: {e}") from e


async def load_flow_from_buffer(zip_buffer: bytes) -> dict[str, Any]:
    """
    Load a .zv1 file from raw ZIP data in memory.

    Args:
        zip_buffer: Raw ZIP data as bytes.

    Returns:
        Extracted flow object.

    Raises:
        ValueError: If buffer is invalid.
    """
    # Validate ZIP signature
    if len(zip_buffer) < 4 or zip_buffer[:2] != b"PK":
        raise ValueError("Invalid ZIP data: Missing ZIP file signature")

    try:
        import io

        with zipfile.ZipFile(io.BytesIO(zip_buffer), "r") as zf:
            return await _parse_zv1_zip(zf)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP data: {e}") from e


async def _parse_zv1_zip(zf: zipfile.ZipFile) -> dict[str, Any]:
    """
    Parse a .zv1 ZIP file and extract flow data.

    Args:
        zf: ZipFile object.

    Returns:
        Flow data dict.
    """
    # Find orchestration.json
    orchestration_name = None
    for name in zf.namelist():
        if name in ("orchestration.json", "./orchestration.json"):
            orchestration_name = name
            break

    if orchestration_name is None:
        raise ValueError("Missing required orchestration.json file in .zv1 archive")

    # Parse orchestration.json
    with zf.open(orchestration_name) as f:
        orchestration_content = f.read().decode("utf-8")

    try:
        orchestration_data = json.loads(orchestration_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in orchestration.json: {e}") from e

    # Validate structure
    if not isinstance(orchestration_data.get("nodes"), list):
        raise ValueError('orchestration.json must contain a "nodes" array')
    if not isinstance(orchestration_data.get("links"), list):
        raise ValueError('orchestration.json must contain a "links" array')

    # Handle imports
    imports: list[dict[str, Any]] = []

    if orchestration_data.get("imports"):
        if isinstance(orchestration_data["imports"], list):
            # Legacy format
            imports = orchestration_data["imports"]
        elif isinstance(orchestration_data["imports"], dict):
            # New format
            imports = await _load_zv1_imports_from_object(
                orchestration_data["imports"], zf
            )

    # Handle knowledge.db (optional)
    knowledge_db_path = None
    for name in zf.namelist():
        if name in ("knowledge.db", "./knowledge.db"):
            # Extract to temp directory
            temp_dir = Path(tempfile.gettempdir()) / ".zv1_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            flow_id = orchestration_data.get("id", "unknown")
            knowledge_db_path = temp_dir / f"knowledge_{flow_id}.db"

            with zf.open(name) as src:
                knowledge_db_path.write_bytes(src.read())
            break

    return {
        **orchestration_data,
        "imports": imports,
        "knowledge_db_path": str(knowledge_db_path) if knowledge_db_path else None,
    }


async def _load_zv1_imports_from_object(
    imports_object: dict[str, str],
    zf: zipfile.ZipFile,
) -> list[dict[str, Any]]:
    """
    Load imports from the new imports object format.

    Args:
        imports_object: Dict mapping import IDs to snapshots.
        zf: ZipFile object.

    Returns:
        List of import definitions.
    """
    imports: list[dict[str, Any]] = []

    # Find all import folder entries
    import_entries = [
        name
        for name in zf.namelist()
        if name.startswith("imports/") and name != "imports/" and not name.endswith("/")
    ]

    # Group by folder name
    import_folders: dict[str, list[str]] = {}
    for entry in import_entries:
        parts = entry.split("/")
        if len(parts) >= 2:
            folder_name = parts[1]
            if folder_name not in import_folders:
                import_folders[folder_name] = []
            import_folders[folder_name].append(entry)

    # Load each import
    for import_id, snapshot in imports_object.items():
        # Find matching folder
        folder_name = _find_import_folder(import_id, snapshot, import_folders)

        if folder_name is None:
            raise ValueError(f"Import '{import_id}' with snapshot '{snapshot}' not found")

        import_data = await _load_zv1_import_folder(folder_name, zf)
        import_data["import_id"] = import_id
        import_data["requested_snapshot"] = snapshot
        imports.append(import_data)

    return imports


def _find_import_folder(
    import_id: str,
    version_range: str,
    import_folders: dict[str, list[str]],
) -> str | None:
    """Find the import folder matching the given import ID."""
    # Look for exact match
    if import_id in import_folders:
        return import_id

    # Look for partial match
    for folder_name in import_folders:
        if import_id in folder_name:
            return folder_name

    return None


async def _load_zv1_import_folder(
    folder_name: str,
    zf: zipfile.ZipFile,
) -> dict[str, Any]:
    """Load an import folder from a .zv1 file."""
    orchestration_path = f"imports/{folder_name}/orchestration.json"

    if orchestration_path not in zf.namelist():
        raise ValueError(f"Missing orchestration.json in import folder '{folder_name}'")

    with zf.open(orchestration_path) as f:
        content = f.read().decode("utf-8")

    try:
        orchestration_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in import folder '{folder_name}/orchestration.json': {e}"
        ) from e

    # Validate structure
    if not isinstance(orchestration_data.get("nodes"), list):
        raise ValueError(
            f"Import folder '{folder_name}' orchestration.json must contain a 'nodes' array"
        )
    if not isinstance(orchestration_data.get("links"), list):
        raise ValueError(
            f"Import folder '{folder_name}' orchestration.json must contain a 'links' array"
        )

    import_id = orchestration_data.get("id", folder_name)
    display_name = orchestration_data.get("metadata", {}).get("display_name", import_id)
    snapshot = orchestration_data.get("metadata", {}).get("snapshot", "unknown")

    # Handle knowledge.db for this import
    knowledge_db_path = None
    kb_path = f"imports/{folder_name}/knowledge.db"
    if kb_path in zf.namelist():
        temp_dir = Path(tempfile.gettempdir()) / ".zv1_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        knowledge_db_path = temp_dir / f"knowledge_{import_id}.db"

        with zf.open(kb_path) as src:
            knowledge_db_path.write_bytes(src.read())

    return {
        "id": f"imported-{import_id}",
        "display_name": display_name,
        "snapshot": snapshot,
        "unique_id": import_id,
        "folder_name": folder_name,
        "nodes": orchestration_data["nodes"],
        "links": orchestration_data["links"],
        "imports": [],  # Nested imports would be handled here
        "knowledge_db_path": str(knowledge_db_path) if knowledge_db_path else None,
        **orchestration_data,
    }


def convert_legacy_imports(legacy_imports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert legacy imports array to the new unified format.

    Args:
        legacy_imports: List of legacy import objects.

    Returns:
        List of converted import definitions.
    """
    if not isinstance(legacy_imports, list):
        return []

    result: list[dict[str, Any]] = []

    for index, legacy_import in enumerate(legacy_imports):
        unique_id = legacy_import.get("id", f"legacy-import-{index}")
        display_name = legacy_import.get(
            "display_name", legacy_import.get("name", f"Legacy Import {index + 1}")
        )
        snapshot = legacy_import.get("snapshot", "legacy")

        result.append(
            {
                "id": f"imported-{unique_id}",
                "display_name": display_name,
                "snapshot": snapshot,
                "unique_id": unique_id,
                "folder_name": f"{display_name}.{snapshot}.{unique_id}",
                "nodes": legacy_import.get("nodes", []),
                "links": legacy_import.get("links", []),
                "imports": convert_legacy_imports(legacy_import.get("imports", [])),
                **legacy_import,
            }
        )

    return result
