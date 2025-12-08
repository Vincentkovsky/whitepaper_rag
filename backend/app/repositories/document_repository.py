from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.document import Document, DocumentSource, DocumentStatus

# SQLAlchemy ORM model
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func
from ..core.database import Base


class DocumentModel(Base):
    """Document ORM model for PostgreSQL"""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)
    source_value = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PostgresDocumentRepository:
    """PostgreSQL implementation of document repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        """Create a new document"""
        db_doc = DocumentModel(
            id=document.id,
            user_id=UUID(document.user_id),
            source_type=document.source_type.value,
            source_value=str(document.source_value),
            storage_path=str(document.storage_path) if document.storage_path else None,
            title=document.title,
            status=document.status.value,
            error_message=document.error_message,
            created_at=datetime.fromisoformat(document.created_at) if document.created_at else None,
            updated_at=datetime.fromisoformat(document.updated_at) if document.updated_at else None,
        )
        self.session.add(db_doc)
        await self.session.commit()
        await self.session.refresh(db_doc)
        return document

    async def get(self, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        db_doc = result.scalar_one_or_none()
        if not db_doc:
            return None
        return self._to_domain(db_doc)

    async def list_by_user(self, user_id: str) -> List[Document]:
        """List all documents for a user"""
        result = await self.session.execute(
            select(DocumentModel)
            .where(DocumentModel.user_id == UUID(user_id))
            .order_by(DocumentModel.created_at.desc())
        )
        db_docs = result.scalars().all()
        return [self._to_domain(db_doc) for db_doc in db_docs]

    async def delete(self, document_id: str) -> bool:
        """Delete a document"""
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        db_doc = result.scalar_one_or_none()
        if not db_doc:
            return False
        await self.session.delete(db_doc)
        await self.session.commit()
        return True

    async def mark_status(
        self, document_id: str, status: DocumentStatus, error_message: Optional[str] = None
    ) -> None:
        """Update document status"""
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        db_doc = result.scalar_one_or_none()
        if db_doc:
            db_doc.status = status.value
            if error_message is not None:
                db_doc.error_message = error_message
            await self.session.commit()

    async def update_title(self, document_id: str, title: str) -> None:
        """Update document title"""
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        db_doc = result.scalar_one_or_none()
        if db_doc:
            db_doc.title = title
            await self.session.commit()

    def _to_domain(self, db_doc: DocumentModel) -> Document:
        """Convert ORM model to domain model"""
        return Document(
            id=db_doc.id,
            user_id=str(db_doc.user_id),
            source_type=DocumentSource(db_doc.source_type),
            source_value=db_doc.source_value,
            storage_path=Path(db_doc.storage_path) if db_doc.storage_path else None,
            title=db_doc.title,
            status=DocumentStatus(db_doc.status),
            error_message=db_doc.error_message,
            created_at=db_doc.created_at.isoformat() if db_doc.created_at else None,
            updated_at=db_doc.updated_at.isoformat() if db_doc.updated_at else None,
        )
