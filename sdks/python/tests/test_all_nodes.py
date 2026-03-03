"""
Test runner for all nodes in the zv1 engine.

Usage:
    python -m pytest tests/test_all_nodes.py -v
    python tests/test_all_nodes.py --node add
    python tests/test_all_nodes.py --start-from array-map
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.loaders import load_integrations


@dataclass
class TestResults:
    """Track test results."""

    passed: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)


# Custom test functions
class CustomTests:
    """Custom test functions for special validation."""

    @staticmethod
    def shuffle_test(result: dict[str, Any], test_case: dict[str, Any]) -> bool:
        """Test that shuffle produces a valid shuffled array."""
        input_arr = test_case.get("inputs", {}).get("array", [])
        output_arr = result.get("array", [])

        # Check length
        if len(output_arr) != len(input_arr):
            return False

        # Check that all elements from input are in output
        for item in input_arr:
            if item not in output_arr:
                return False

        # Check that all elements from output are in input
        for item in output_arr:
            if item not in input_arr:
                return False

        # If array has more than 3 elements, check order is different
        if len(input_arr) > 3:
            same_order = all(input_arr[i] == output_arr[i] for i in range(len(input_arr)))
            if same_order:
                return False

        return True

    @staticmethod
    def seed_shuffle_test(result: dict[str, Any], test_case: dict[str, Any]) -> bool:
        """Test seeded shuffle - just check it's a valid shuffle."""
        return CustomTests.shuffle_test(result, test_case)


CUSTOM_TESTS = {
    "shuffleTest": CustomTests.shuffle_test,
    "seedShuffleTest": CustomTests.seed_shuffle_test,
}


def substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute ${VAR} patterns with environment variable values.

    Args:
        obj: The object to process (can be string, list, dict, or other).

    Returns:
        The object with environment variables substituted.
    """
    if isinstance(obj, str):
        return re.sub(
            r"\$\{([^}]+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            obj,
        )
    if isinstance(obj, list):
        return [substitute_env_vars(item) for item in obj]
    if isinstance(obj, dict):
        return {key: substitute_env_vars(value) for key, value in obj.items()}
    return obj


def get_nodes_dir() -> Path:
    """Get the nodes directory path."""
    sdk_root = Path(__file__).parent.parent
    return sdk_root.parent.parent / "nodes"


async def load_process_function(process_path: Path) -> Any:
    """
    Dynamically load a process function from a Python file.

    Args:
        process_path: Path to the .process.py file.

    Returns:
        The process function.
    """
    if not process_path.exists():
        raise FileNotFoundError(f"Process file not found: {process_path}")

    spec = importlib.util.spec_from_file_location(
        f"node_{process_path.stem}", process_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {process_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "process"):
        raise AttributeError(f"No 'process' function in {process_path}")

    return module.process


async def run_node_test(
    config: dict[str, Any],
    node_dir: Path,
    test_case: dict[str, Any],
    test_results: TestResults,
) -> bool:
    """
    Run a single test case for a node.

    Args:
        config: Engine configuration with integrations.
        node_dir: Path to the node directory.
        test_case: Test case definition.
        test_results: Test results tracker.

    Returns:
        True if test passed, False otherwise.
    """
    node_name = node_dir.name
    config_path = node_dir / f"{node_name}.config.json"
    process_path = node_dir / f"{node_name}.process.py"

    description = test_case.get("description", "Unknown test")

    if not config_path.exists() or not process_path.exists():
        error = f"Missing config or process file in: {node_dir}"
        print(f"✖ {description} - {error}")
        test_results.failures.append(
            {"node": node_name, "test": description, "error": error}
        )
        return False

    try:
        process_function = await load_process_function(process_path)
        with open(config_path) as f:
            node_config = json.load(f)
    except Exception as e:
        error = f"Failed to load node: {e}"
        print(f"✖ {description} - {error}")
        test_results.failures.append(
            {"node": node_name, "test": description, "error": error}
        )
        return False

    # Substitute environment variables in inputs (e.g., ${AIRTABLE_TEST_BASE_ID})
    substituted_inputs = substitute_env_vars(test_case.get("inputs", {}))

    # Merge default values from node_config into inputs
    inputs_with_defaults = dict(substituted_inputs)
    for input_def in node_config.get("inputs", []):
        name = input_def.get("name")
        if (
            name
            and inputs_with_defaults.get(name) is None
            and input_def.get("default") is not None
        ):
            inputs_with_defaults[name] = input_def["default"]

    # Substitute environment variables in settings as well
    substituted_settings = substitute_env_vars(test_case.get("settings", {}))

    # Apply default settings from node configuration
    settings_with_defaults = dict(substituted_settings)
    for setting_def in node_config.get("settings", []):
        name = setting_def.get("name")
        if (
            name
            and settings_with_defaults.get(name) is None
            and setting_def.get("default") is not None
        ):
            settings_with_defaults[name] = setting_def["default"]

    try:
        result = await process_function(
            inputs=inputs_with_defaults,
            settings=settings_with_defaults,
            config=config,
            node_config=node_config,
        )

        if test_case.get("expectedError"):
            error = "Expected error but none was thrown"
            print(f"✖ {description} - {error}")
            test_results.failures.append(
                {"node": node_name, "test": description, "error": error}
            )
            return False

        # Handle custom test functions
        custom_test_name = test_case.get("customTest")
        if custom_test_name and custom_test_name in CUSTOM_TESTS:
            passed = CUSTOM_TESTS[custom_test_name](result, test_case)
            if passed:
                print(f"✔ {description}")
                test_results.passed += 1
                return True
            else:
                error = "Custom test function failed"
                print(f"✖ {description} - {error}")
                test_results.failures.append(
                    {"node": node_name, "test": description, "error": error}
                )
                return False

        # Check against expectedSchema if provided
        if test_case.get("expectedSchema"):
            validation_errors = validate_schema(result, test_case["expectedSchema"])
            if validation_errors:
                error = f"Schema validation failed: {', '.join(validation_errors)}"
                print(f"✖ {description} - Schema validation failed:")
                for err in validation_errors:
                    print(f"  - {err}")
                test_results.failures.append(
                    {"node": node_name, "test": description, "error": error}
                )
                return False

            print(f"✔ {description} (schema validation)")
            test_results.passed += 1
            return True

        # Regular expected value testing
        if test_case.get("expected"):
            for key, expected_value in test_case["expected"].items():
                actual_value = result.get(key)
                if actual_value != expected_value:
                    error = (
                        f"Mismatch for {key}: expected {json.dumps(expected_value)}, "
                        f"got {json.dumps(actual_value)}"
                    )
                    print(f"✖ {description} - {error}")
                    test_results.failures.append(
                        {"node": node_name, "test": description, "error": error}
                    )
                    return False
        elif not custom_test_name and not test_case.get("expectedSchema"):
            print(
                f"⚠ {description} - No validation criteria provided "
                "(expected, expectedSchema, or customTest)"
            )

        print(f"✔ {description}")
        test_results.passed += 1
        return True

    except Exception as err:
        if test_case.get("expectedError"):
            if str(err) == test_case["expectedError"]:
                print(f"✔ {description}")
                test_results.passed += 1
                return True
            else:
                error = (
                    f"Error mismatch: expected '{test_case['expectedError']}', "
                    f"got '{str(err)}'"
                )
                print(f"✖ {description} - {error}")
                test_results.failures.append(
                    {"node": node_name, "test": description, "error": error}
                )
                return False
        else:
            error = str(err) or "Unexpected error occurred"
            print(f"✖ {description} - Unexpected error:")
            print(f"  {err}")
            test_results.failures.append(
                {"node": node_name, "test": description, "error": error}
            )
            return False


def validate_schema(
    result: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """
    Validate result against expected schema.

    Args:
        result: The actual result.
        schema: Expected schema definition.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    for key, constraints in schema.items():
        if key not in result:
            errors.append(f"Missing expected output: {key}")
            continue

        value = result[key]

        # Check type constraints
        if "type" in constraints:
            types = (
                constraints["type"]
                if isinstance(constraints["type"], list)
                else [constraints["type"]]
            )

            type_valid = False
            for expected_type in types:
                if expected_type == "number" and isinstance(value, (int, float)):
                    type_valid = True
                elif expected_type == "string" and isinstance(value, str):
                    type_valid = True
                elif expected_type == "boolean" and isinstance(value, bool):
                    type_valid = True
                elif (
                    expected_type == "object"
                    and isinstance(value, dict)
                    and value is not None
                ):
                    type_valid = True
                elif expected_type == "array" and isinstance(value, list):
                    type_valid = True
                elif expected_type == "null" and value is None:
                    type_valid = True

            if not type_valid:
                errors.append(
                    f"Type mismatch for {key}: expected {constraints['type']}, "
                    f"got {type(value).__name__}"
                )

        # Check numeric constraints
        if isinstance(value, (int, float)):
            if (
                "minimum" in constraints
                and value < constraints["minimum"]
            ):
                errors.append(
                    f"Value {value} for {key} is less than minimum {constraints['minimum']}"
                )
            if (
                "maximum" in constraints
                and value > constraints["maximum"]
            ):
                errors.append(
                    f"Value {value} for {key} is greater than maximum {constraints['maximum']}"
                )

        # Check string constraints
        if isinstance(value, str) and "pattern" in constraints:
            if not re.match(constraints["pattern"], value):
                errors.append(
                    f'Value "{value}" for {key} does not match pattern {constraints["pattern"]}'
                )

        # Check array constraints
        if isinstance(value, list):
            if (
                "minItems" in constraints
                and len(value) < constraints["minItems"]
            ):
                errors.append(
                    f"Array {key} has fewer items ({len(value)}) than required ({constraints['minItems']})"
                )
            if (
                "maxItems" in constraints
                and len(value) > constraints["maxItems"]
            ):
                errors.append(
                    f"Array {key} has more items ({len(value)}) than allowed ({constraints['maxItems']})"
                )

    return errors


async def run_tests(node_filter: str | None = None, start_from: str | None = None):
    """
    Run all node tests.

    Args:
        node_filter: Specific node to test (optional).
        start_from: Start testing from this node (optional).
    """
    # Load environment variables
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    nodes_dir = get_nodes_dir()
    if not nodes_dir.exists():
        print(f"Nodes directory not found: {nodes_dir}")
        sys.exit(1)

    # Get sorted list of node directories
    node_dirs = sorted([d.name for d in nodes_dir.iterdir() if d.is_dir()])

    # Load integrations
    integrations = await load_integrations(
        {
            "keys": {
                "openrouter": os.environ.get("OPENROUTER_API_KEY"),
                "newsdata_io": os.environ.get("NEWSDATA_IO_API_KEY"),
                "airtable": os.environ.get("AIRTABLE_API_KEY"),
                "notion": os.environ.get("NOTION_API_KEY"),
            }
        }
    )

    config = {"integrations": integrations}

    # Determine which nodes to test
    if node_filter and start_from:
        print("Error: Cannot specify both --node and --start-from options")
        sys.exit(1)

    if node_filter:
        if node_filter not in node_dirs:
            print(f'Node "{node_filter}" not found in nodes directory.')
            print(f"Available nodes: {', '.join(node_dirs[:20])}...")
            sys.exit(1)
        nodes_to_test = [node_filter]
        print(f"Running tests for single node: {node_filter}")
    elif start_from:
        if start_from not in node_dirs:
            print(f'Node "{start_from}" not found in nodes directory.')
            sys.exit(1)
        start_idx = node_dirs.index(start_from)
        nodes_to_test = node_dirs[start_idx:]
        print(
            f"Running tests starting from node: {start_from} ({len(nodes_to_test)} nodes total)"
        )
    else:
        nodes_to_test = node_dirs
        print(f"Running tests for all {len(nodes_to_test)} nodes")

    # Initialize test results
    test_results = TestResults()

    for node_name in nodes_to_test:
        node_dir = nodes_dir / node_name
        tests_path = node_dir / f"{node_name}.tests.json"

        if not tests_path.exists():
            continue

        try:
            with open(tests_path) as f:
                tests = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing tests for {node_name}: {e}")
            continue

        print(f"Running tests for node: {node_name}")

        for test_case in tests:
            try:
                await run_node_test(config, node_dir, test_case, test_results)
            except Exception as err:
                description = test_case.get("description", "Unknown test")
                print(f"✖ {description} - Fatal error: {err}")
                test_results.failures.append(
                    {
                        "node": node_name,
                        "test": description,
                        "error": str(err) or "Fatal error occurred",
                    }
                )

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = test_results.passed + len(test_results.failures)
    print(f"Total tests run: {total_tests}")
    print(f"Passed: {test_results.passed}")
    print(f"Failed: {len(test_results.failures)}")

    if test_results.failures:
        print("\nFAILED TESTS:")
        print("-" * 40)
        for failure in test_results.failures:
            print(f"{failure['node']}: {failure['test']}")
            print(f"  Error: {failure['error']}")
            print("")

        print(f"❌ {len(test_results.failures)} test(s) failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run tests for zv1 nodes")
    parser.add_argument("--node", help="Run tests for a specific node only")
    parser.add_argument(
        "--start-from", help="Run tests for all nodes starting from the specified node"
    )

    args = parser.parse_args()

    asyncio.run(run_tests(node_filter=args.node, start_from=args.start_from))


if __name__ == "__main__":
    main()
