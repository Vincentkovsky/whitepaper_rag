from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from functools import lru_cache

try:
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None

from pathlib import Path

from ..core.config import get_settings
from ..models.document import DocumentStatus, DocumentSource
from ..repositories.document_repository import LocalDocumentRepository
from ..services.chunking_service import SemanticChunker
from ..services.embedding_service import EmbeddingService

settings = get_settings()
celery_app = (
    Celery(
        "blockchain_rag",
        broker=settings.celery_broker_url,
        backend=settings.redis_url,
    )
    if Celery
    else None
)

logger = logging.getLogger(__name__)

repo = LocalDocumentRepository(store_path=settings.storage_base_path.parent / "documents.json")


@lru_cache(maxsize=1)
def get_chunker() -> SemanticChunker:
    return SemanticChunker()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingService:
    return EmbeddingService()


def _parse_document(document_id: str, user_id: str, source_url: Optional[str] = None) -> None:
    """
    Placeholder parse task – in real implementation this would call Unstructured,
    chunk the document, and push embeddings into Chroma.
    """
    logger.info("Starting parse_document_task", extra={"document_id": document_id})
    repo.mark_status(document_id, DocumentStatus.parsing)

    document = repo.get(document_id)
    if not document:
        logger.error("Document not found", extra={"document_id": document_id})
        return

    if document.source_type == DocumentSource.pdf and document.storage_path:
        elements = get_chunker().parse_pdf(Path(document.storage_path))
    elif document.source_type == DocumentSource.url:
        elements = get_chunker().parse_html(document.source_value)
    else:
        elements = get_chunker().parse_plain_text(document.source_value)

    sections = get_chunker().build_sections(elements)
    chunks = get_chunker().chunk_sections(sections)

    chunks_path = settings.storage_base_path.parent / "chunks" / f"{document_id}.json"
    get_chunker().serialize_chunks(chunks, chunks_path)

    get_embedder().embed_chunks(document_id=document_id, user_id=user_id, chunks_file=chunks_path)

    repo.mark_status(document_id, DocumentStatus.completed)
    logger.info("Completed parse_document_task", extra={"document_id": document_id})


if celery_app:

    @celery_app.task(name="documents.parse")
    def parse_document_task(document_id: str, user_id: str, source_url: Optional[str] = None) -> None:
        _parse_document(document_id, user_id, source_url)

else:

    def parse_document_task(document_id: str, user_id: str, source_url: Optional[str] = None) -> None:
        _parse_document(document_id, user_id, source_url)


def enqueue_parse_document(document_id: str, user_id: str, source_url: Optional[str] = None) -> None:
    """Helper to run Celery task or fallback inline for dev."""
    if celery_app and not settings.run_tasks_inline:
        parse_document_task.delay(document_id, user_id, source_url)
    else:
        parse_document_task(document_id, user_id, source_url)

