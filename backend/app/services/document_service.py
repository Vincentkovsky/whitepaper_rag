import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from ..core.config import Settings, get_settings
from ..models.document import Document, DocumentSource, DocumentStatus
from ..repositories.document_repository import DocumentRepository
from ..tasks.document_tasks import enqueue_parse_document
from ..services.embedding_service import EmbeddingService


class DocumentService:
    def __init__(
        self,
        repo: DocumentRepository,
        settings: Optional[Settings] = None,
        embedder: Optional[EmbeddingService] = None,
    ):
        self.repo = repo
        self.settings = settings or get_settings()
        self._embedder = embedder

    def upload_pdf(self, file: UploadFile, user_id: str) -> Document:
        if file.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件")

        document_id = str(uuid.uuid4())
        storage_path = self._build_storage_path(user_id, document_id, ".pdf")
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        with storage_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document = Document(
            id=document_id,
            user_id=user_id,
            source_type=DocumentSource.pdf,
            source_value=storage_path.name,
            storage_path=storage_path,
        )
        self.repo.create(document)
        if self.settings.document_pipeline_enabled:
            enqueue_parse_document(document_id=document_id, user_id=user_id)
        else:
            self.repo.mark_status(document_id, DocumentStatus.completed)
        return document

    def submit_url(self, url: str, user_id: str) -> Document:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL 格式不正确")

        document_id = str(uuid.uuid4())
        document = Document(
            id=document_id,
            user_id=user_id,
            source_type=DocumentSource.url,
            source_value=url,
        )
        self.repo.create(document)
        if self.settings.document_pipeline_enabled:
            enqueue_parse_document(document_id=document_id, user_id=user_id, source_url=url)
        else:
            self.repo.mark_status(document_id, DocumentStatus.completed)
        return document

    def list_documents(self, user_id: str):
        return self.repo.list_by_user(user_id)

    def get_document(self, document_id: str, user_id: str) -> Document:
        document = self.repo.get(document_id)
        if not document or document.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        return document

    def delete_document(self, document_id: str, user_id: str) -> None:
        document = self.get_document(document_id, user_id)
        if document.storage_path:
            path = Path(document.storage_path)
            path.unlink(missing_ok=True)

        chunks_path = self._chunks_path(document_id)
        chunks_path.unlink(missing_ok=True)

        self.repo.delete(document_id)

        embedder = self._get_embedder()
        embedder.delete_document_vectors(document_id=document_id, user_id=user_id)

    def _build_storage_path(self, user_id: str, document_id: str, suffix: str) -> Path:
        base: Path = self.settings.storage_base_path
        return base / user_id / f"{document_id}{suffix}"

    def _chunks_path(self, document_id: str) -> Path:
        return self.settings.storage_base_path.parent / "chunks" / f"{document_id}.json"

    def _get_embedder(self) -> EmbeddingService:
        if self._embedder is None:
            self._embedder = EmbeddingService()
        return self._embedder

