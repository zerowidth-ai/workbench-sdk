"""
Flow Test Runner for the zv1 Python engine.

Supports two test file formats:

1. Legacy JSON format (embedded flow):
   - File: flow.combined-testing.json
   - Structure: { "flow": {...}, "inputs": {...}, "expected": {...} }

2. New .zv1 format (separate test metadata):
   - File: flow.zv1-test.zv1 (the actual .zv1 file)
   - Metadata: flow.zv1-test.test.json (test configuration)
   - Structure: { "inputs": {...}, "expected": {...}, "expectedSchema": {...} }

Usage:
    python tests/test_flows.py                    # Run all flow tests
    python tests/test_flows.py flow.addition.json # Run a single test
    python tests/test_flows.py flow.addition.zv1  # Run a .zv1 test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import Zv1


@dataclass
class TestResults:
    """Track test results."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)


def get_flows_dir() -> Path:
    """Get the flows directory path."""
    return Path(__file__).parent / "flows"


def validate_against_schema(result: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """
    Validate result against expected schema.

    Args:
        result: The actual result.
        schema: Expected JSON schema.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Basic schema validation - check required properties exist and types match
    if "properties" in schema:
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name not in result:
                if prop_name in schema.get("required", []):
                    errors.append(f"Missing required property: {prop_name}")
                continue

            value = result[prop_name]
            expected_type = prop_schema.get("type")

            if expected_type:
                type_valid = False
                types = [expected_type] if isinstance(expected_type, str) else expected_type

                for t in types:
                    if t == "string" and isinstance(value, str):
                        type_valid = True
                    elif t == "number" and isinstance(value, (int, float)):
                        type_valid = True
                    elif t == "integer" and isinstance(value, int):
                        type_valid = True
                    elif t == "boolean" and isinstance(value, bool):
                        type_valid = True
                    elif t == "array" and isinstance(value, list):
                        type_valid = True
                    elif t == "object" and isinstance(value, dict):
                        type_valid = True
                    elif t == "null" and value is None:
                        type_valid = True

                if not type_valid:
                    errors.append(
                        f"Type mismatch for {prop_name}: expected {expected_type}, "
                        f"got {type(value).__name__}"
                    )

    return errors


async def run_flow_test(test_file: str, test_results: TestResults) -> bool:
    """
    Run a single flow test.

    Args:
        test_file: Name of the test file.
        test_results: Test results tracker.

    Returns:
        True if test passed, False otherwise.
    """
    flows_dir = get_flows_dir()
    test_path = flows_dir / test_file

    # Determine test format and load accordingly
    if test_file.endswith(".zv1"):
        # New .zv1 format with companion .test.json
        test_metadata_path = test_path.with_suffix(".test.json")

        if not test_metadata_path.exists():
            print(f"[SKIP] No test metadata found for {test_file}, skipping...")
            test_results.skipped += 1
            return True

        with open(test_metadata_path) as f:
            test_data = json.load(f)

        flow = str(test_path)  # Use file path for .zv1 files
        inputs = test_data.get("inputs", {})
        expected = test_data.get("expected")
        expected_schema = test_data.get("expectedSchema")
        expected_error = test_data.get("expectedError")

    elif test_file.endswith(".json") and not test_file.endswith(".test.json"):
        # Legacy JSON format with embedded flow
        with open(test_path) as f:
            test_data = json.load(f)

        flow = test_data.get("flow")
        if not flow:
            print(f"[SKIP] No flow found in {test_file}, skipping...")
            test_results.skipped += 1
            return True

        inputs = test_data.get("inputs", {})
        expected = test_data.get("expected")
        expected_schema = test_data.get("expectedSchema")
        expected_error = test_data.get("expectedError")

    else:
        # Skip non-test files
        return True

    print(f"[INFO] Testing flow: {test_file} with inputs: {json.dumps(inputs)}")

    try:
        # Load environment variables
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        # Create engine
        engine = await Zv1.create(
            flow,
            {
                "debug": False,
                "keys": {
                    "openrouter": os.environ.get("OPENROUTER_API_KEY"),
                    "google_custom_search": {
                        "key": os.environ.get("GOOGLE_CUSTOM_SEARCH_KEY"),
                        "cx": os.environ.get("GOOGLE_CUSTOM_SEARCH_CX"),
                    },
                },
            },
        )

        # Run the flow
        result = await engine.run(inputs)

        # Convert ExecutionResult to dict for comparison
        result_dict = {
            "outputs": result.outputs,
            "timeline": result.timeline,  # Already a list of dicts
            "cost_summary": result.cost_summary,
            "message": result.message,
        }

        print(f"  [RESULT] {json.dumps(result_dict)}")

        # If we expected an error but got success, that's a failure
        if expected_error:
            print(f"  [FAIL] Expected error but flow succeeded for {test_file}")
            test_results.failed += 1
            test_results.failures.append({
                "file": test_file,
                "error": "Expected error but flow succeeded",
            })
            return False

        # Check expected output
        if expected is not None:
            if result.outputs != expected:
                error_msg = (
                    f"Output mismatch: expected {json.dumps(expected)}, "
                    f"got {json.dumps(result.outputs)}"
                )
                print(f"  [FAIL] {test_file} - {error_msg}")
                test_results.failed += 1
                test_results.failures.append({
                    "file": test_file,
                    "error": error_msg,
                    "expected": expected,
                    "actual": result.outputs,
                })
                return False

        # Check expected schema
        elif expected_schema is not None:
            validation_errors = validate_against_schema(result_dict, expected_schema)
            if validation_errors:
                error_msg = f"Schema validation failed: {', '.join(validation_errors)}"
                print(f"  [FAIL] {test_file} - {error_msg}")
                test_results.failed += 1
                test_results.failures.append({
                    "file": test_file,
                    "error": error_msg,
                })
                return False

        print(f"  [PASS] {test_file}")
        test_results.passed += 1

        # Cleanup
        await engine.cleanup()

        return True

    except Exception as err:
        # If we expected an error, check if it matches
        if expected_error:
            error_type = getattr(err, "error_type", None)
            error_message = str(err)

            print(f"  [EXPECTED ERROR] {test_file}")
            print(f"    Error Type: {error_type or 'Unknown'}")
            print(f"    Error Message: {error_message}")

            # Validate error details if specified
            if expected_error.get("type") and error_type != expected_error["type"]:
                print(
                    f"    [FAIL] Expected error type '{expected_error['type']}' "
                    f"but got '{error_type}'"
                )
                test_results.failed += 1
                test_results.failures.append({
                    "file": test_file,
                    "error": f"Error type mismatch",
                })
                return False

            if expected_error.get("message") and expected_error["message"] not in error_message:
                print(
                    f"    [FAIL] Expected error message to contain "
                    f"'{expected_error['message']}' but got '{error_message}'"
                )
                test_results.failed += 1
                test_results.failures.append({
                    "file": test_file,
                    "error": f"Error message mismatch",
                })
                return False

            print(f"    [PASS] Error matches expectations")
            test_results.passed += 1
            return True

        # Unexpected error
        print(f"  [FAIL] {test_file}")
        print(f"    Error: {err}")
        test_results.failed += 1
        test_results.failures.append({
            "file": test_file,
            "error": str(err),
        })
        return False


async def run_all_tests() -> TestResults:
    """Run all flow tests."""
    flows_dir = get_flows_dir()
    test_results = TestResults()

    if not flows_dir.exists():
        print(f"[ERROR] Flows directory not found: {flows_dir}")
        sys.exit(1)

    # Get all test files (.json and .zv1, but not .test.json)
    test_files = sorted([
        f.name for f in flows_dir.iterdir()
        if (f.suffix == ".json" and not f.name.endswith(".test.json"))
        or f.suffix == ".zv1"
    ])

    print(f"[INFO] Running all flow tests ({len(test_files)} files)")

    for test_file in test_files:
        try:
            await run_flow_test(test_file, test_results)
        except Exception as err:
            print(f"  [FAIL] {test_file} - Fatal error: {err}")
            test_results.failed += 1
            test_results.failures.append({
                "file": test_file,
                "error": f"Fatal error: {err}",
            })

    return test_results


async def run_single_test(filename: str) -> TestResults:
    """Run a single flow test."""
    flows_dir = get_flows_dir()
    test_path = flows_dir / filename
    test_results = TestResults()

    if not test_path.exists():
        print(f"[ERROR] Test file not found: {filename}")
        print(f"Available test files:")
        for f in sorted(flows_dir.iterdir()):
            if (f.suffix == ".json" and not f.name.endswith(".test.json")) or f.suffix == ".zv1":
                print(f"  - {f.name}")
        sys.exit(1)

    print(f"[INFO] Running single flow test: {filename}")

    try:
        await run_flow_test(filename, test_results)
    except Exception as err:
        print(f"  [FAIL] {filename} - Fatal error: {err}")
        test_results.failed += 1
        test_results.failures.append({
            "file": filename,
            "error": f"Fatal error: {err}",
        })

    return test_results


def print_summary(test_results: TestResults) -> None:
    """Print test summary."""
    print("\n" + "=" * 60)
    print("FLOW TEST SUMMARY")
    print("=" * 60)

    total = test_results.passed + test_results.failed + test_results.skipped
    print(f"Total tests: {total}")
    print(f"Passed: {test_results.passed}")
    print(f"Failed: {test_results.failed}")
    print(f"Skipped: {test_results.skipped}")

    if test_results.failures:
        print("\nFAILED TESTS:")
        print("-" * 40)
        for failure in test_results.failures:
            print(f"{failure['file']}: {failure['error']}")
        print("")
        print(f"❌ {test_results.failed} test(s) failed!")
    else:
        print("\n✅ All tests passed!")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run flow tests for zv1 engine")
    parser.add_argument(
        "filename",
        nargs="?",
        help="Specific test file to run (optional)",
    )

    args = parser.parse_args()

    if args.filename:
        test_results = await run_single_test(args.filename)
    else:
        test_results = await run_all_tests()

    print_summary(test_results)

    if test_results.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
