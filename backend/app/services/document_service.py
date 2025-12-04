import logging
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, get_settings
from ..models.document import Document, DocumentSource, DocumentStatus
from ..repositories.document_repository import PostgresDocumentRepository
from ..services.embedding_service import EmbeddingService
from ..services.subscription_service import SubscriptionService, get_subscription_service
from ..tasks.document_tasks import TaskPriority, enqueue_parse_document


class DocumentService:
    """Service for document operations"""

    def __init__(
        self,
        repo: PostgresDocumentRepository,
        settings: Optional[Settings] = None,
        embedder: Optional[EmbeddingService] = None,
        subscription_service: Optional[SubscriptionService] = None,
    ):
        self.repo = repo
        self.settings = settings or get_settings()
        self.embedder = embedder or EmbeddingService()
        self.subscription = subscription_service or get_subscription_service()
        self.logger = logging.getLogger(__name__)

    async def upload_pdf(
        self,
        file: UploadFile,
        user_id: str,
        priority: TaskPriority = TaskPriority.STANDARD,
    ) -> Document:
        """Upload and process a PDF file"""
        document_id = str(uuid4())

        try:
            # Consume credits
            self.subscription.consume_credits(user_id, "document_upload_pdf")
            self.logger.info("Credits consumed", extra={"user_id": user_id, "document_id": document_id})

            # Save file
            storage_path = self.settings.storage_base_path / user_id / f"{document_id}.pdf"
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            content = await file.read()
            with open(storage_path, "wb") as f:
                f.write(content)

            # Create document record
            document = Document(
                id=document_id,
                user_id=user_id,
                source_type=DocumentSource.pdf,
                source_value=storage_path.name,
                storage_path=storage_path,
            )

            await self.repo.create(document)

            if self.settings.document_pipeline_enabled:
                # Enqueue for processing (will use Celery)
                enqueue_parse_document(
                    document_id=document_id,
                    user_id=user_id,
                    priority=priority,
                    sku="document_upload_pdf",
                )
            else:
                await self.repo.mark_status(document_id, DocumentStatus.completed)
                self.logger.info(
                    "Document upload scheduled",
                    extra={
                        "document_id": document_id,
                        "user_id": user_id,
                        "priority": priority.value,
                        "pipeline_enabled": self.settings.document_pipeline_enabled,
                    },
                )
            return document
        except Exception as exc:
            if not getattr(exc, "credits_refunded", False):
                self.subscription.refund_credits(user_id, "document_upload_pdf", reason="upload_failed")
            self.logger.exception(
                "Failed to upload PDF",
                extra={"document_id": document_id, "user_id": user_id},
            )
            raise

    async def submit_url(
        self,
        url: str,
        user_id: str,
        priority: TaskPriority = TaskPriority.STANDARD,
    ) -> Document:
        """Submit a URL for processing"""
        document_id = str(uuid4())

        try:
            # Consume credits
            self.subscription.consume_credits(user_id, "document_upload_url")
            self.logger.info("Credits consumed", extra={"user_id": user_id, "document_id": document_id})

            # Create document record
            document = Document(
                id=document_id,
                user_id=user_id,
                source_type=DocumentSource.url,
                source_value=url,
            )

            await self.repo.create(document)

            if self.settings.document_pipeline_enabled:
                # Enqueue for processing
                enqueue_parse_document(
                    document_id=document_id,
                    user_id=user_id,
                    source_url=url,
                    priority=priority,
                    sku="document_upload_url",
                )
            else:
                await self.repo.mark_status(document_id, DocumentStatus.completed)

            return document
        except Exception as exc:
            if not getattr(exc, "credits_refunded", False):
                self.subscription.refund_credits(user_id, "document_upload_url", reason="upload_failed")
            self.logger.exception(
                "Failed to submit URL",
                extra={"document_id": document_id, "user_id": user_id},
            )
            raise

    async def list_documents(self, user_id: str, **kwargs) -> List[Document]:
        """List all documents for a user"""
        return await self.repo.list_by_user(user_id)

    async def get_document(self, document_id: str, user_id: str, **kwargs) -> Document:
        """Get a specific document"""
        document = await self.repo.get(document_id)
        if not document or document.user_id != user_id:
            raise ValueError("Document not found or access denied")
        return document

    async def delete_document(self, document_id: str, user_id: str, **kwargs) -> None:
        """Delete a document"""
        self.logger.info("Deleting document", extra={"document_id": document_id, "user_id": user_id})

        document = await self.repo.get(document_id)
        if not document or document.user_id != user_id:
            raise ValueError("Document not found or access denied")

        # Delete vectors
        self.embedder.delete_document_vectors(document_id, user_id)

        # Delete from database
        await self.repo.delete(document_id)

    async def get_document_status(self, document_id: str, user_id: str, **kwargs) -> dict:
        """Get document processing status"""
        document = await self.repo.get(document_id)
        if not document or document.user_id != user_id:
            raise ValueError("Document not found or access denied")

        return {
            "document_id": document_id,
            "status": document.status,
            "error_message": document.error_message,
        }
