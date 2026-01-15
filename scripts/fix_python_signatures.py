#!/usr/bin/env python3
"""
Fix Python process file signatures to use keyword-only arguments and type hints.
"""

import os
import re
from pathlib import Path

NODES_DIR = Path(__file__).parent.parent / "nodes"

OLD_SIGNATURE = "async def process(inputs, settings, config, nodeConfig):"
NEW_SIGNATURE = """async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:"""

TYPING_IMPORT = "from typing import Any"


def fix_python_file(file_path: Path) -> tuple[bool, list[str]]:
    """
    Fix a Python process file.

    Returns:
        Tuple of (was_modified, list_of_changes)
    """
    changes = []

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Fix 1: Replace old signature with new signature
    if OLD_SIGNATURE in content:
        content = content.replace(OLD_SIGNATURE, NEW_SIGNATURE)
        changes.append("Fixed function signature")

    # Fix 2: Add typing import if missing and signature was updated
    if "dict[str, Any]" in content and TYPING_IMPORT not in content:
        # Find where to insert the import
        lines = content.split("\n")
        insert_idx = 0

        # Skip shebang, docstrings at top
        for i, line in enumerate(lines):
            if line.startswith("#!") or line.startswith('"""') or line.startswith("'''"):
                # Skip past docstrings
                if line.startswith('"""') or line.startswith("'''"):
                    quote = line[:3]
                    if line.count(quote) >= 2:
                        # Single line docstring
                        insert_idx = i + 1
                    else:
                        # Multi-line docstring, find end
                        for j in range(i + 1, len(lines)):
                            if quote in lines[j]:
                                insert_idx = j + 1
                                break
                else:
                    insert_idx = i + 1
            elif line.startswith("import ") or line.startswith("from "):
                insert_idx = i
                break
            elif line.strip() and not line.startswith("#"):
                break

        # Insert the import
        lines.insert(insert_idx, TYPING_IMPORT)
        if insert_idx < len(lines) - 1 and lines[insert_idx + 1].strip():
            # Add blank line after import if next line is not blank
            if not lines[insert_idx + 1].startswith("import ") and not lines[insert_idx + 1].startswith("from "):
                lines.insert(insert_idx + 1, "")
        content = "\n".join(lines)
        changes.append("Added typing import")

    # Fix 3: Replace nodeConfig with node_config in the body
    # Use word boundary to avoid partial matches
    if re.search(r'\bnodeConfig\b', content):
        content = re.sub(r'\bnodeConfig\b', 'node_config', content)
        changes.append("Renamed nodeConfig to node_config")

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        return True, changes

    return False, []


def main():
    """Fix all Python process files in the nodes directory."""
    if not NODES_DIR.exists():
        print(f"Error: Nodes directory not found: {NODES_DIR}")
        return

    print(f"Scanning {NODES_DIR} for Python process files...")

    fixed_count = 0
    error_count = 0

    for node_dir in sorted(NODES_DIR.iterdir()):
        if not node_dir.is_dir():
            continue

        process_file = node_dir / f"{node_dir.name}.process.py"
        if not process_file.exists():
            continue

        try:
            modified, changes = fix_python_file(process_file)
            if modified:
                fixed_count += 1
                print(f"  Fixed: {node_dir.name}")
                for change in changes:
                    print(f"    - {change}")
        except Exception as e:
            error_count += 1
            print(f"  Error: {node_dir.name}: {e}")

    print(f"\nSummary:")
    print(f"  Fixed: {fixed_count} files")
    print(f"  Errors: {error_count} files")


if __name__ == "__main__":
    main()
