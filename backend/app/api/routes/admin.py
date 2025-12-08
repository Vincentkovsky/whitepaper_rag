from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID

from ...core.security import UserContext, get_current_user
from ...core.database import get_db
from ...services.embedding_service import EmbeddingService
from ...repositories.user_repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_embedding_service_dep() -> EmbeddingService:
    return EmbeddingService()


# ============== User Management ==============

class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None


@router.get("/users")
async def list_users(
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all users (admin only)"""
    # TODO: Add admin role check
    user_repo = UserRepository(db)
    users = await user_repo.list_all()
    return [user.to_dict() for user in users]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: UUID,
    update_data: UserUpdateRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update user status (admin only)"""
    # TODO: Add admin role check
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    if update_data.is_superuser is not None:
        user.is_superuser = update_data.is_superuser
    
    updated_user = await user_repo.update(user)
    await db.commit()
    return updated_user.to_dict()


# ============== ChromaDB Management ==============

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

