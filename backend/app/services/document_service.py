import logging
import mimetypes
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from ..core.config import Settings, get_settings
from ..logging_utils import bind_document_context
from ..models.document import Document, DocumentSource, DocumentStatus
from ..repositories.document_repository import DocumentRepository
from ..services.embedding_service import EmbeddingService
from ..services.subscription_service import CREDIT_PRICING, SubscriptionService, get_subscription_service
from ..tasks.document_tasks import enqueue_parse_document
from ..tasks.priority import TaskPriority


class DocumentService:
    def __init__(
        self,
        repo: DocumentRepository,
        settings: Optional[Settings] = None,
        embedder: Optional[EmbeddingService] = None,
        subscription_service: Optional[SubscriptionService] = None,
    ):
        self.repo = repo
        self.settings = settings or get_settings()
        self._embedder = embedder
        self.subscription = subscription_service or get_subscription_service()
        self.logger = logging.getLogger("app.services.document")

    def upload_pdf(
        self,
        file: UploadFile,
        user_id: str,
        priority: TaskPriority = TaskPriority.STANDARD,
        access_token: Optional[str] = None,
    ) -> Document:
        if file.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件")

        self._ensure_credits(user_id, "document_upload_pdf")

        document_id = str(uuid.uuid4())
        bind_document_context(document_id)
        storage_path = self._build_storage_path(user_id, document_id, ".pdf")
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.logger.info(
                "Uploading PDF document",
                extra={"document_id": document_id, "user_id": user_id, "original_filename": file.filename},
            )
            with storage_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            document = Document(
                id=document_id,
                user_id=user_id,
                source_type=DocumentSource.pdf,
                source_value=storage_path.name,
                storage_path=storage_path,
            )
            with self._repo_token(access_token):
                self.repo.create(document)
                if self.settings.document_pipeline_enabled:
                    enqueue_parse_document(
                        document_id=document_id,
                        user_id=user_id,
                        priority=priority,
                        sku="document_upload_pdf",
                    )
                else:
                    self.repo.mark_status(document_id, DocumentStatus.completed)
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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    def submit_url(
        self,
        url: str,
        user_id: str,
        priority: TaskPriority = TaskPriority.STANDARD,
        access_token: Optional[str] = None,
    ) -> Document:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL 格式不正确")

        self._ensure_credits(user_id, "document_upload_url")

        document_id = str(uuid.uuid4())
        bind_document_context(document_id)
        try:
            document = Document(
                id=document_id,
                user_id=user_id,
                source_type=DocumentSource.url,
                source_value=url,
            )
            with self._repo_token(access_token):
                self.repo.create(document)
                if self.settings.document_pipeline_enabled:
                    enqueue_parse_document(
                        document_id=document_id,
                        user_id=user_id,
                        source_url=url,
                        priority=priority,
                        sku="document_upload_url",
                    )
                else:
                    self.repo.mark_status(document_id, DocumentStatus.completed)
                self.logger.info(
                    "URL submitted for processing",
                    extra={
                        "document_id": document_id,
                        "user_id": user_id,
                        "source_url": url,
                        "priority": priority.value,
                    },
                )
                return document
        except Exception as exc:
            if not getattr(exc, "credits_refunded", False):
                self.subscription.refund_credits(user_id, "document_upload_url", reason="upload_failed")
            self.logger.exception(
                "Failed to submit URL",
                extra={"document_id": document_id, "user_id": user_id, "source_url": url},
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    def list_documents(self, user_id: str, access_token: Optional[str] = None):
        with self._repo_token(access_token):
            return self.repo.list_by_user(user_id)

    def get_document(self, document_id: str, user_id: str, access_token: Optional[str] = None) -> Document:
        with self._repo_token(access_token):
            document = self.repo.get(document_id)
            if not document or document.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
            return document

    def get_document_status(self, document_id: str, user_id: str, access_token: Optional[str] = None) -> dict:
        document = self.get_document(document_id, user_id, access_token=access_token)
        return {
            "document_id": document.id,
            "status": document.status,
            "error_message": document.error_message,
        }

    def delete_document(self, document_id: str, user_id: str, access_token: Optional[str] = None) -> None:
        bind_document_context(document_id)
        document = self.get_document(document_id, user_id, access_token=access_token)
        if document.storage_path:
            path = Path(document.storage_path)
            path.unlink(missing_ok=True)

        chunks_path = self._chunks_path(document_id)
        chunks_path.unlink(missing_ok=True)

        with self._repo_token(access_token):
            self.repo.delete(document_id)

        self.logger.info("Deleting document", extra={"document_id": document_id, "user_id": user_id})
        embedder = self._get_embedder()
        embedder.delete_document_vectors(document_id=document_id, user_id=user_id)
        sku = "document_upload_pdf" if document.source_type == DocumentSource.pdf else "document_upload_url"
        if sku in CREDIT_PRICING:
            self.subscription.refund_credits(user_id, sku, reason="document_deleted")

    def _build_storage_path(self, user_id: str, document_id: str, suffix: str) -> Path:
        base: Path = self.settings.storage_base_path
        return base / user_id / f"{document_id}{suffix}"

    def _chunks_path(self, document_id: str) -> Path:
        return self.settings.storage_base_path.parent / "chunks" / f"{document_id}.json"

    def _get_embedder(self) -> EmbeddingService:
        if self._embedder is None:
            self._embedder = EmbeddingService()
        return self._embedder

    def _ensure_credits(self, user_id: str, sku: str) -> None:
        allowed = self.subscription.check_and_consume(user_id, sku)
        if allowed:
            self.logger.info("Credits consumed", extra={"user_id": user_id, "sku": sku})
            return
        usage = self.subscription.get_usage(user_id)
        remaining = usage.get("remaining_credits", 0)
        self.logger.warning(
            "Insufficient credits",
            extra={"user_id": user_id, "sku": sku, "remaining": remaining},
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} ，请升级订阅或等待重置。",
        )

    @contextmanager
    def _repo_token(self, access_token: Optional[str]):
        setter = getattr(self.repo, "set_access_token", None)
        if callable(setter):
            setter(access_token)
        try:
            yield
        finally:
            if callable(setter):
                setter(None)

