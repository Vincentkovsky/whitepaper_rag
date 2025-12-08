"""
Document Search Tool for the Agent.

Provides document retrieval functionality by integrating with RAGService.
"""

import logging
from typing import Any, Dict, List, Optional

from ..types import Tool, ToolSchema
from ...services.rag_service import RAGService


logger = logging.getLogger("app.agent.tools.document_search")


def create_document_search_tool(rag_service: RAGService) -> Tool:
    """Create a document_search tool instance.
    
    Args:
        rag_service: The RAGService instance to use for retrieval
        
    Returns:
        A Tool instance configured for document search
    """
    
    def document_search(
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks in documents.
        
        Args:
            query: The search query
            user_id: ID of the user making the request
            document_id: ID of the document to search (optional, searches all user documents if not provided)
            k: Number of results to return (default: 10)
            
        Returns:
            List of relevant chunks with text and metadata
        """
        logger.debug(
            f"Document search: query='{query[:50]}...', "
            f"document_id={document_id or 'all'}, user_id={user_id}, k={k}"
        )
        
        try:
            chunks = rag_service.get_relevant_chunks(
                question=query,
                document_id=document_id,  # Will be None to search all documents
                user_id=user_id,
                k=k,
            )
            
            # Format results for agent consumption
            results = []
            for chunk in chunks:
                results.append({
                    "id": chunk.get("id"),
                    "text": chunk.get("text", ""),
                    "document_id": chunk.get("metadata", {}).get("document_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section_path", "unknown"),
                    "page": chunk.get("metadata", {}).get("page_number"),
                    "relevance_score": 1.0 - chunk.get("distance", 0.0),  # Convert distance to score
                })
            
            logger.info(f"Document search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise
    
    schema = ToolSchema(
        name="document_search",
        description=(
            "Search for relevant information across the user's documents. "
            "Use this tool when you need to find specific information, "
            "facts, or context from documents. Searches all user documents by default."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant content",
                },
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user making the request",
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional: The ID of a specific document to search (omit to search all user documents)",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10)",
                    "default": 10,
                },
            },
        },
        required=["query", "user_id"],
    )
    
    return Tool(schema=schema, handler=document_search)
