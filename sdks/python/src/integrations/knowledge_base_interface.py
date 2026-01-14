"""
Standard interface for knowledge base integrations.

All knowledge base integrations must implement this interface
to ensure compatibility across different backends (SQLite, Pinecone, Weaviate, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class KnowledgeBaseInterface(ABC):
    """
    Abstract base class for knowledge base integrations.
    """

    @abstractmethod
    async def query(
        self,
        query: str,
        params: list[Any] | None = None,
        operation: str = "SELECT",
    ) -> dict[str, Any]:
        """
        Execute a raw query against the knowledge base.

        Args:
            query: SQL or query string.
            params: Query parameters.
            operation: Type of operation (SELECT, INSERT, UPDATE, DELETE).

        Returns:
            Query result.
        """
        raise NotImplementedError(
            "query() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def select(
        self, query: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a SELECT query.

        Args:
            query: SQL SELECT query.
            params: Query parameters.

        Returns:
            Query results.
        """
        raise NotImplementedError(
            "select() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def insert(
        self, query: str, params: list[Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute an INSERT query.

        Args:
            query: SQL INSERT query.
            params: Query parameters.

        Returns:
            Insert result with last_id.
        """
        raise NotImplementedError(
            "insert() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def update(
        self, query: str, params: list[Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute an UPDATE query.

        Args:
            query: SQL UPDATE query.
            params: Query parameters.

        Returns:
            Update result with changes count.
        """
        raise NotImplementedError(
            "update() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def delete(
        self, query: str, params: list[Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a DELETE query.

        Args:
            query: SQL DELETE query.
            params: Query parameters.

        Returns:
            Delete result with changes count.
        """
        raise NotImplementedError(
            "delete() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def semantic_search(
        self, query: str, options: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Text query to search for.
            options: Search options (limit, similarity_threshold, document_id).

        Returns:
            Search results with similarity scores.
        """
        raise NotImplementedError(
            "semantic_search() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def get_embedding_model(self) -> str:
        """
        Get the embedding model used by this knowledge base.

        Returns:
            Embedding model name.
        """
        raise NotImplementedError(
            "get_embedding_model() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """
        Get basic statistics about the knowledge base.

        Returns:
            Statistics object.
        """
        raise NotImplementedError(
            "get_stats() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def validate_schema(self) -> dict[str, Any]:
        """
        Validate the knowledge base schema.

        Returns:
            Validation result.
        """
        raise NotImplementedError(
            "validate_schema() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """
        Get database schema information.

        Returns:
            Schema information.
        """
        raise NotImplementedError(
            "get_schema() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the knowledge base.
        """
        raise NotImplementedError(
            "connect() method must be implemented by knowledge base integration"
        )

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the knowledge base and clean up resources.
        """
        raise NotImplementedError(
            "disconnect() method must be implemented by knowledge base integration"
        )
