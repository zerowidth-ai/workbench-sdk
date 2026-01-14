"""
Cache management utilities for the zv1 engine.

Provides a consistent interface for reading and writing cache values,
making it easy to change cache structure/format without modifying core logic.

Cache Structure:
    Each cache key stores a LIST of DICTS with value + metadata:
    [
        {"value": "hello", "timestamp": 1234567890},
        {"value": "world", "timestamp": 1234567891}
    ]

This enables:
    - Value history tracking
    - Refiring input support (consume only NEW values)
    - Non-refiring inputs (always use latest, can reuse consumed values)
    - Debugging and time-travel

Consumption Tracking:
    Tracked per-node, per-input in node.settings._consumption_tracking
    Only used for refiring inputs - non-refiring inputs ignore it
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """A single cache entry with value and metadata."""

    value: Any
    timestamp: int  # High-resolution timestamp in nanoseconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {"value": self.value, "timestamp": self.timestamp}


class CacheManager:
    """
    Manages the execution cache for node outputs.

    Uses a dict-based store where each key maps to a list of CacheEntry objects.
    Each entry has {value, timestamp}.

    Methods:
        - set(): appends new entry with current timestamp
        - get(): returns the most recent value
        - get_new(): returns values newer than a timestamp (for refiring)
    """

    def __init__(self) -> None:
        """Initialize an empty cache store."""
        self._store: dict[str, list[CacheEntry]] = {}

    def _generate_key(self, node_id: str, port_name: str) -> str:
        """Generate a cache key from node_id and port_name."""
        return f"{node_id}:{port_name}"

    def _ensure_key(self, key: str) -> None:
        """Ensure a key exists in the store with an empty list."""
        if key not in self._store:
            self._store[key] = []

    def _get_timestamp(self) -> int:
        """Get a high-resolution timestamp in nanoseconds."""
        return time.time_ns()

    def set(
        self,
        *,
        node_id: str,
        port_name: str,
        value: Any,
    ) -> None:
        """
        Set a value in the cache (appends to the value list with timestamp).

        Args:
            node_id: The node ID.
            port_name: The port/output name.
            value: The value to store.
        """
        key = self._generate_key(node_id, port_name)
        self._ensure_key(key)

        entry = CacheEntry(value=value, timestamp=self._get_timestamp())
        self._store[key].append(entry)

    def get(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> Any | None:
        """
        Get the most recent value from the cache.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            The most recent cached value, or None if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return None

        return entries[-1].value

    def get_entry(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> CacheEntry | None:
        """
        Get the most recent entry (with metadata) from the cache.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            The most recent CacheEntry, or None if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return None

        return entries[-1]

    def get_new(
        self,
        *,
        node_id: str,
        port_name: str,
        after_timestamp: int,
    ) -> list[Any]:
        """
        Get new values that arrived after a specific timestamp (for refiring inputs).

        Args:
            node_id: The node ID.
            port_name: The port/output name.
            after_timestamp: Only return values newer than this timestamp.

        Returns:
            List of values that are newer than the timestamp.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return []

        return [entry.value for entry in entries if entry.timestamp > after_timestamp]

    def get_latest_timestamp(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> int | None:
        """
        Get the timestamp of the most recent value.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            The timestamp of the most recent value, or None if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return None

        return entries[-1].timestamp

    def has(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> bool:
        """
        Check if a value exists in the cache.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            True if the key exists and has at least one value.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)
        return bool(entries)

    def has_new(
        self,
        *,
        node_id: str,
        port_name: str,
        after_timestamp: int,
    ) -> bool:
        """
        Check if there are new values after a specific timestamp (for refiring).

        Args:
            node_id: The node ID.
            port_name: The port/output name.
            after_timestamp: Check for values newer than this timestamp.

        Returns:
            True if there are values newer than the timestamp.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return False

        return any(entry.timestamp > after_timestamp for entry in entries)

    def delete(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> bool:
        """
        Delete a value from the cache.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            True if the key existed and was deleted.
        """
        key = self._generate_key(node_id, port_name)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all values from the cache."""
        self._store.clear()

    def get_node_outputs(self, node_id: str) -> dict[str, Any]:
        """
        Get all cache entries for a specific node (most recent values only).

        Args:
            node_id: The node ID.

        Returns:
            Dict with port_name keys and their most recent values.
        """
        outputs: dict[str, Any] = {}
        prefix = f"{node_id}:"

        for key, entries in self._store.items():
            if key.startswith(prefix) and entries:
                port_name = key[len(prefix) :]
                outputs[port_name] = entries[-1].value

        return outputs

    def get_history(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> list[Any]:
        """
        Get the full history of values for a specific cache entry.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            List of all values (oldest to newest), empty list if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)
        return [entry.value for entry in entries] if entries else []

    def get_history_with_metadata(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> list[dict[str, Any]]:
        """
        Get the full history with metadata for a specific cache entry.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            List of all entries as dicts (oldest to newest), empty list if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)
        return [entry.to_dict() for entry in entries] if entries else []

    def get_node_history(self, node_id: str) -> dict[str, list[Any]]:
        """
        Get all values (history) for all outputs of a specific node.

        Args:
            node_id: The node ID.

        Returns:
            Dict with port_name keys and their full history lists.
        """
        history: dict[str, list[Any]] = {}
        prefix = f"{node_id}:"

        for key, entries in self._store.items():
            if key.startswith(prefix):
                port_name = key[len(prefix) :]
                history[port_name] = [entry.value for entry in entries]

        return history

    def pop(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> Any | None:
        """
        Pop the most recent value from the cache (removes and returns it).

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            The most recent value, or None if not found.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)

        if not entries:
            return None

        entry = entries.pop()
        return entry.value

    def get_history_length(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> int:
        """
        Get the number of values stored for a specific cache entry.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            Number of values in the history.
        """
        key = self._generate_key(node_id, port_name)
        entries = self._store.get(key)
        return len(entries) if entries else 0

    def get_key(
        self,
        *,
        node_id: str,
        port_name: str,
    ) -> str:
        """
        Get the raw cache key.

        Args:
            node_id: The node ID.
            port_name: The port/output name.

        Returns:
            The cache key.
        """
        return self._generate_key(node_id, port_name)

    def get_raw_store(self) -> dict[str, list[CacheEntry]]:
        """
        Get access to the underlying store (use sparingly).

        Returns:
            The cache store.
        """
        return self._store

    def get_all_keys(self) -> list[str]:
        """
        Get all cache keys.

        Returns:
            List of all cache keys.
        """
        return list(self._store.keys())

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Cache statistics including total keys, total entries,
            and average history length.
        """
        total_keys = len(self._store)
        total_entries = sum(len(entries) for entries in self._store.values())

        return {
            "total_keys": total_keys,
            "total_entries": total_entries,
            "average_history_length": (
                round(total_entries / total_keys, 2) if total_keys > 0 else 0
            ),
        }

    # Static helper methods for consumption tracking

    @staticmethod
    def get_consumption_tracking(node_settings: dict[str, Any] | None) -> dict[str, int]:
        """
        Get consumption tracking for a node.

        Args:
            node_settings: The node's settings dict.

        Returns:
            The consumption tracking dict (or empty if not exists).
        """
        if node_settings is None:
            return {}
        return node_settings.get("_consumption_tracking", {})

    @staticmethod
    def update_consumption_tracking(
        node_settings: dict[str, Any] | None,
        input_name: str,
        timestamp: int,
    ) -> dict[str, Any]:
        """
        Create updated consumption tracking for a node input.

        Args:
            node_settings: The node's settings dict.
            input_name: The input port name.
            timestamp: The timestamp to mark as consumed.

        Returns:
            Dict with updated consumption tracking to merge into settings.
        """
        existing = {}
        if node_settings is not None:
            existing = node_settings.get("_consumption_tracking", {})

        return {"_consumption_tracking": {**existing, input_name: timestamp}}

    @staticmethod
    def get_last_consumed(
        node_settings: dict[str, Any] | None,
        input_name: str,
    ) -> int:
        """
        Get the last consumed timestamp for a specific input.

        Args:
            node_settings: The node's settings dict.
            input_name: The input port name.

        Returns:
            The last consumed timestamp, or 0 if never consumed.
        """
        if node_settings is None:
            return 0
        tracking = node_settings.get("_consumption_tracking", {})
        return tracking.get(input_name, 0)
