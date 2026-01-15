"""
Get Chunk By Index Node - Retrieves a specific chunk from the knowledge base.
"""

import json
from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Get Chunk By Index node.
    """
    try:
        # Get knowledge base integration
        integrations = config.get("integrations", {})
        knowledge_base = integrations.get("knowledgeBase") or integrations.get("sqlite")

        if not knowledge_base:
            raise ValueError(
                "Knowledge base integration not found. Make sure a knowledge database is available."
            )

        document_id = inputs.get("document_id")
        chunk_index = inputs.get("chunk_index")

        if not document_id or not isinstance(document_id, str):
            raise ValueError("Document ID is required and must be a string")

        if chunk_index is None or not isinstance(chunk_index, (int, float)):
            raise ValueError("Chunk index is required and must be a number")

        # Query for the specific chunk
        query = """
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
                c.created_at,
                d.display_name as document_name,
                d.file_type,
                d.folder_path
            FROM chunks c
            LEFT JOIN documents d ON c.document_id = d.id
            WHERE c.document_id = ? AND c.chunk_index = ?
            LIMIT 1
        """

        results = await knowledge_base.select(query, [document_id, int(chunk_index)])

        if not results or (isinstance(results, list) and len(results) == 0):
            return {"chunk": None, "found": False, "error": None}

        chunk = results[0] if isinstance(results, list) else results

        # Parse metadata if it exists
        if chunk.get("metadata"):
            try:
                chunk["metadata"] = json.loads(chunk["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass  # Keep original value if parsing fails

        return {"chunk": chunk, "found": True, "error": None}

    except Exception as e:
        # Return error information instead of throwing to prevent engine crash
        return {"chunk": None, "found": False, "error": str(e)}
