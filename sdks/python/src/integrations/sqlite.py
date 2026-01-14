"""
SQLite Integration for the zv1 engine.

Provides access to SQLite databases with vector search support via sqlite-vec.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from src.integrations.knowledge_base_interface import KnowledgeBaseInterface

logger = logging.getLogger(__name__)

try:
    import aiosqlite

    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

try:
    import sqlite_vec

    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False


class SQLiteIntegration(KnowledgeBaseInterface):
    """
    Integration with SQLite databases.

    Supports vector similarity search via sqlite-vec extension.
    """

    def __init__(
        self,
        db_path: str | Path,
        timeout: float = 5.0,
    ) -> None:
        """
        Initialize the SQLite integration.

        Args:
            db_path: Path to the SQLite database file.
            timeout: Query timeout in seconds.
        """
        if not HAS_AIOSQLITE:
            raise ImportError(
                "aiosqlite package is required for SQLite integration. "
                "Install with: pip install aiosqlite"
            )

        self.db_path = str(db_path)
        self.timeout = timeout
        self.db: aiosqlite.Connection | None = None
        self.is_connected = False
        self._has_vec_extension = False

    async def connect(self) -> None:
        """
        Initialize the database connection.

        Raises:
            Exception: If connection fails.
        """
        try:
            # Check if database file exists
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"Database file not found: {self.db_path}")

            # Create database connection
            self.db = await aiosqlite.connect(self.db_path, timeout=self.timeout)
            self.db.row_factory = aiosqlite.Row

            # Load sqlite-vec extension if available
            if HAS_SQLITE_VEC:
                try:
                    await self.db.enable_load_extension(True)
                    sqlite_vec.load(self.db._connection)
                    self._has_vec_extension = True
                except Exception as e:
                    logger.warning(f"Failed to load sqlite-vec extension: {e}")
                    self._has_vec_extension = False

            # Test the connection
            async with self.db.execute("SELECT 1") as cursor:
                await cursor.fetchone()

            self.is_connected = True

        except Exception as e:
            self.is_connected = False
            raise Exception(f"SQLite connection failed: {e}") from e

    async def disconnect(self) -> None:
        """
        Close the database connection and clean up temporary files.
        """
        if self.db and self.is_connected:
            try:
                await self.db.close()
                self.is_connected = False
            except Exception as e:
                raise Exception(f"Failed to close database: {e}") from e

        # Clean up temporary file if it exists
        if self.db_path and (".temp" in self.db_path or "knowledge_" in self.db_path):
            try:
                if os.path.exists(self.db_path):
                    os.unlink(self.db_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {self.db_path}: {e}")

    async def query(
        self,
        query: str,
        params: list[Any] | None = None,
        operation: str = "SELECT",
    ) -> dict[str, Any]:
        """
        Execute a raw SQL query.

        Args:
            query: SQL query to execute.
            params: Query parameters for parameterized queries.
            operation: Type of operation (SELECT, INSERT, UPDATE, DELETE).

        Returns:
            Query result.

        Raises:
            Exception: On query errors.
        """
        if not self.is_connected:
            await self.connect()

        if params is None:
            params = []

        try:
            # Basic SQL injection prevention
            allowed_operations = [
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "CREATE",
                "DROP",
                "ALTER",
            ]
            query_upper = query.strip().upper()
            is_allowed = any(query_upper.startswith(op) for op in allowed_operations)

            if not is_allowed:
                raise Exception(f"Operation not allowed: {query_upper.split()[0]}")

            # Execute query based on operation type
            if operation.upper() == "SELECT":
                async with self.db.execute(query, params) as cursor:
                    if "LIMIT 1" in query_upper:
                        row = await cursor.fetchone()
                        result = dict(row) if row else None
                    else:
                        rows = await cursor.fetchall()
                        result = [dict(row) for row in rows]
            else:
                async with self.db.execute(query, params) as cursor:
                    await self.db.commit()
                    result = {
                        "lastrowid": cursor.lastrowid,
                        "rowcount": cursor.rowcount,
                    }

            row_count = (
                result.get("rowcount", 0)
                if isinstance(result, dict)
                else len(result) if isinstance(result, list) else 0
            )

            return {
                "success": True,
                "data": result,
                "operation": operation.upper(),
                "row_count": row_count,
            }

        except Exception as e:
            raise Exception(f"SQLite query failed: {e}") from e

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
        result = await self.query(query, params, "SELECT")
        data = result.get("data")
        if data is None:
            return []
        if isinstance(data, list):
            return data
        return [data] if data else []

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
        result = await self.query(query, params, "INSERT")
        return {
            "success": result.get("success", False),
            "last_id": result.get("data", {}).get("lastrowid"),
            "changes": result.get("data", {}).get("rowcount"),
        }

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
        result = await self.query(query, params, "UPDATE")
        return {
            "success": result.get("success", False),
            "changes": result.get("data", {}).get("rowcount"),
        }

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
        result = await self.query(query, params, "DELETE")
        return {
            "success": result.get("success", False),
            "changes": result.get("data", {}).get("rowcount"),
        }

    async def get_schema(self) -> dict[str, list[dict[str, Any]]]:
        """
        Get database schema information.

        Returns:
            Schema information keyed by table name.
        """
        tables = await self.select(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )

        schema: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            columns = await self.select(f"PRAGMA table_info({table['name']})")
            schema[table["name"]] = columns

        return schema

    async def validate_schema(self) -> dict[str, Any]:
        """
        Check if the database has the expected knowledge base schema.

        Returns:
            Schema validation result.
        """
        return await self.validate_knowledge_base_schema()

    async def validate_knowledge_base_schema(self) -> dict[str, Any]:
        """
        Check if the database has the expected knowledge base schema.

        Returns:
            Schema validation result.
        """
        try:
            schema = await self.get_schema()

            has_documents = "documents" in schema
            has_chunks = "chunks" in schema

            if not has_documents or not has_chunks:
                return {
                    "valid": False,
                    "missing": {
                        "documents": not has_documents,
                        "chunks": not has_chunks,
                    },
                }

            # Check for required columns in documents table
            doc_columns = [col["name"] for col in schema["documents"]]
            required_doc_columns = [
                "id",
                "display_name",
                "file_type",
                "file_size",
                "created_by",
                "created_at",
                "updated_at",
            ]
            missing_doc_columns = [
                col for col in required_doc_columns if col not in doc_columns
            ]

            # Check for required columns in chunks table
            chunk_columns = [col["name"] for col in schema["chunks"]]
            required_chunk_columns = [
                "id",
                "document_id",
                "chunk_index",
                "content",
                "created_at",
                "updated_at",
            ]
            missing_chunk_columns = [
                col for col in required_chunk_columns if col not in chunk_columns
            ]

            return {
                "valid": len(missing_doc_columns) == 0
                and len(missing_chunk_columns) == 0,
                "missing": {
                    "documents": missing_doc_columns,
                    "chunks": missing_chunk_columns,
                },
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def get_stats(self) -> dict[str, Any]:
        """
        Get basic statistics about the knowledge base.

        Returns:
            Knowledge base statistics.
        """
        try:
            doc_count = await self.select("SELECT COUNT(*) as count FROM documents")
            chunk_count = await self.select("SELECT COUNT(*) as count FROM chunks")
            total_size = await self.select(
                "SELECT SUM(file_size) as total_size FROM documents"
            )

            return {
                "documents": doc_count[0].get("count", 0) if doc_count else 0,
                "chunks": chunk_count[0].get("count", 0) if chunk_count else 0,
                "total_size": total_size[0].get("total_size", 0) if total_size else 0,
            }
        except Exception as e:
            raise Exception(f"Failed to get knowledge base stats: {e}") from e

    async def get_embedding_model(self) -> str:
        """
        Get the embedding model used by this knowledge base.

        Returns:
            Embedding model name.
        """
        try:
            recent_chunk = await self.select(
                """
                SELECT embedding_model FROM chunks
                WHERE embedding_model IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """
            )

            if recent_chunk and recent_chunk[0].get("embedding_model"):
                return recent_chunk[0]["embedding_model"]

            return "text-embedding-3-small"
        except Exception as e:
            logger.warning(
                f"Failed to get embedding model from database, using default: {e}"
            )
            return "text-embedding-3-small"

    async def semantic_search(
        self,
        query: str,
        options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Text query to search for.
            options: Search options (limit, similarity_threshold, document_id,
                    embedding_model, query_embedding).

        Returns:
            Search results with similarity scores.
        """
        if options is None:
            options = {}

        limit = options.get("limit", 10)
        similarity_threshold = options.get("similarity_threshold", 0.7)
        document_id = options.get("document_id")
        embedding_model = options.get("embedding_model")

        try:
            if not self.is_connected:
                await self.connect()

            # Get the embedding model to use
            model_to_use = embedding_model
            if not model_to_use:
                try:
                    model_to_use = await self.get_embedding_model()
                except Exception as e:
                    logger.warning(
                        f"Failed to get embedding model from database, using default: {e}"
                    )
                    model_to_use = "text-embedding-3-small"

            # Check if sqlite-vec extension is loaded
            if not self._has_vec_extension:
                logger.warning(
                    "sqlite-vec extension not loaded, falling back to text search"
                )
                return await self._fallback_text_search(query, options)

            # Check if query embedding is provided
            if "query_embedding" not in options:
                logger.warning(
                    "No query embedding provided, falling back to text search"
                )
                return await self._fallback_text_search(query, options)

            query_embedding = options["query_embedding"]
            embedding_dimensions = len(query_embedding)
            query_embedding_str = json.dumps(query_embedding)

            # Build the KNN query using sqlite-vec scalar functions
            search_sql = """
                SELECT
                    c.id,
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.token_count,
                    c.chunk_type,
                    c.metadata,
                    c.embedding_model,
                    c.embedding_dimensions,
                    c.embedding,
                    c.created_at,
                    d.display_name as document_name,
                    d.file_type,
                    d.folder_path,
                    vec_distance_cosine(c.embedding, ?) as similarity
                FROM chunks c
                LEFT JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                    AND c.embedding_model = ?
                    AND c.embedding_dimensions = ?
                    AND vec_distance_cosine(c.embedding, ?) >= ?
            """

            params: list[Any] = [
                query_embedding_str,
                model_to_use,
                embedding_dimensions,
                query_embedding_str,
                similarity_threshold,
            ]

            if document_id:
                search_sql += " AND c.document_id = ?"
                params.append(document_id)

            search_sql += """
                ORDER BY vec_distance_cosine(c.embedding, ?) ASC
                LIMIT ?
            """
            params.extend([query_embedding_str, limit])

            results = await self.select(search_sql, params)

            # Parse JSON metadata and format results
            return [
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "document_name": row.get("document_name"),
                    "file_type": row.get("file_type"),
                    "folder_path": row.get("folder_path"),
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "token_count": row.get("token_count"),
                    "chunk_type": row.get("chunk_type"),
                    "metadata": json.loads(row["metadata"])
                    if row.get("metadata")
                    else {},
                    "embedding_model": row.get("embedding_model"),
                    "embedding_dimensions": row.get("embedding_dimensions"),
                    "similarity_score": row.get("similarity"),
                    "created_at": row.get("created_at"),
                }
                for row in results
            ]

        except Exception as e:
            logger.warning(f"Vector search failed, falling back to text search: {e}")
            return await self._fallback_text_search(query, options)

    async def _fallback_text_search(
        self, query: str, options: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Fallback text search when vector search is not available.

        Args:
            query: Text query to search for.
            options: Search options.

        Returns:
            Search results with mock similarity scores.
        """
        if options is None:
            options = {}

        limit = options.get("limit", 10)
        document_id = options.get("document_id")

        try:
            sql = """
                SELECT
                    c.id,
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.token_count,
                    c.chunk_type,
                    c.metadata,
                    d.display_name as document_name,
                    d.file_type,
                    d.folder_path,
                    c.created_at
                FROM chunks c
                LEFT JOIN documents d ON c.document_id = d.id
                WHERE c.content LIKE ?
            """

            params: list[Any] = [f"%{query}%"]

            if document_id:
                sql += " AND c.document_id = ?"
                params.append(document_id)

            sql += " ORDER BY c.created_at DESC LIMIT ?"
            params.append(limit)

            results = await self.select(sql, params)

            # Add mock similarity scores for text search
            return [
                {
                    **result,
                    "similarity_score": 1.0 - (i * 0.1),
                    "match_type": "text_search",
                }
                for i, result in enumerate(results)
            ]

        except Exception as e:
            raise Exception(f"Fallback text search failed: {e}") from e
