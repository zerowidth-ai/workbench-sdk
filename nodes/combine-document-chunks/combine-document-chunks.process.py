"""
Combine Document Chunks Node - Combines all chunks of a document into a single text.
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
    Process function for the Combine Document Chunks node.
    """
    try:
        # Get knowledge base integration
        integrations = config.get("integrations", {})
        knowledge_base = integrations.get("knowledgeBase") or integrations.get("sqlite")

        if not knowledge_base:
            raise Exception("Knowledge base integration not found. Make sure a knowledge database is available.")

        document_id = inputs.get("document_id")
        include_metadata = inputs.get("include_metadata", False)
        separator = inputs.get("separator", "\n\n---\n\n")

        if not document_id or not isinstance(document_id, str):
            raise Exception("Document ID is required and must be a string")

        # First, get document information
        document_query = """
            SELECT
                id,
                display_name,
                file_type,
                file_size,
                folder_path,
                created_at,
                updated_at
            FROM documents
            WHERE id = ?
            LIMIT 1
        """

        document_results = await knowledge_base.select(document_query, [document_id])

        if not document_results or (isinstance(document_results, list) and len(document_results) == 0):
            raise Exception(f"Document with ID '{document_id}' not found")

        document_info = document_results[0] if isinstance(document_results, list) else document_results

        # Get all chunks for the document, ordered by chunk_index
        chunks_query = """
            SELECT
                id,
                chunk_index,
                content,
                token_count,
                chunk_type,
                metadata,
                created_at
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
        """

        chunks = await knowledge_base.select(chunks_query, [document_id])

        if not chunks or len(chunks) == 0:
            return {
                "content": "",
                "chunk_count": 0,
                "document_info": document_info,
                "error": None,
            }

        # Combine chunks into markdown content
        combined_chunks = []
        for chunk in chunks:
            chunk_content = chunk.get("content", "")

            # Add metadata if requested
            if include_metadata:
                metadata = {}
                if chunk.get("metadata"):
                    try:
                        metadata = json.loads(chunk["metadata"])
                    except Exception:
                        pass

                metadata_string = ""
                if metadata:
                    metadata_string = f'\n\n<!-- Metadata: {json.dumps(metadata, indent=2)} -->'

                chunk_content = f"## Chunk {chunk.get('chunk_index')}{metadata_string}\n\n{chunk_content}"

            combined_chunks.append(chunk_content)

        combined_content = separator.join(combined_chunks)

        # Add document header
        document_header = (
            f"# {document_info.get('display_name')}\n\n"
            f"*Document ID: {document_info.get('id')}*\n"
            f"*File Type: {document_info.get('file_type')}*\n"
            f"*Chunks: {len(chunks)}*\n\n"
        )

        final_content = document_header + combined_content

        return {
            "content": final_content,
            "chunk_count": len(chunks),
            "document_info": document_info,
            "error": None,
        }

    except Exception as error:
        # Return error information instead of throwing to prevent engine crash
        return {
            "content": "",
            "chunk_count": 0,
            "document_info": None,
            "error": str(error),
        }
