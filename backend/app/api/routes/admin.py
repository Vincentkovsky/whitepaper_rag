from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from ...core.security import UserContext, get_current_user
from ...services.embedding_service import EmbeddingService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_embedding_service_dep() -> EmbeddingService:
    return EmbeddingService()


@router.get("/chroma/documents")
async def list_chroma_documents(
    current_user: UserContext = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
) -> List[Dict[str, Any]]:
    """
    List all documents found in ChromaDB.
    Note: This iterates over all metadata in the collection, so it may be slow for large datasets.
    """
    # TODO: Add admin role check here
    return embedding_service.list_documents()


@router.get("/chroma/documents/{document_id}")
async def get_chroma_document_chunks(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
) -> List[Dict[str, Any]]:
    """
    Get all chunks for a specific document from ChromaDB.
    """
    # TODO: Add admin role check here
    chunks = embedding_service.get_document_chunks(document_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chunks found for document {document_id}"
        )
    return chunks
