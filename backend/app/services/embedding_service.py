from __future__ import annotations

import json
from datetime import datetime, timezone
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

try:
    from google import genai  # type: ignore
except ImportError:  # pragma: no cover
    genai = None

from ..core.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.logger = logging.getLogger("app.services.embedding")
        self.provider = (settings.embedding_provider or "openai").lower()
        chroma_settings = None
        if settings.chroma_server_host:
            self.chroma = chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
                ssl=settings.chroma_server_ssl,
                headers={"Authorization": f"Bearer {settings.chroma_server_api_key}"} if settings.chroma_server_api_key else None,
            )
        elif settings.chroma_persist_directory:
            persist_dir = Path(settings.chroma_persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)
            chroma_settings = ChromaSettings(
                persist_directory=str(persist_dir),
                anonymized_telemetry=False,
            )
            self.chroma = chromadb.PersistentClient(path=str(persist_dir), settings=chroma_settings)
        else:
            chroma_settings = ChromaSettings(anonymized_telemetry=False)
            self.chroma = chromadb.Client(settings=chroma_settings)
        collection_name = settings.chroma_collection or "documents"
        self.collection = self.chroma.get_or_create_collection(collection_name)
        self._openai_client: Optional[OpenAI] = None
        self._gemini_client: Optional["genai.Client"] = None  # type: ignore
        self.batch_size = 100
        self.log_dir = settings.vector_log_dir
        if self.log_dir:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        if self.provider == "gemini":
            self._init_gemini()

    def _client(self) -> OpenAI:
        if self._openai_client is None:
            api_key = self.settings.openai_api_key
            self._openai_client = OpenAI(api_key=api_key) if api_key else OpenAI()
        return self._openai_client

    def _init_gemini(self) -> None:
        if genai is None:  # pragma: no cover
            raise RuntimeError("google-genai is not installed. Run `pip install google-genai`.")
        if not self.settings.google_api_key:
            raise RuntimeError("Missing Google API key for Gemini embeddings.")
        self._gemini_client = genai.Client(api_key=self.settings.google_api_key)

    def embed_chunks(self, document_id: str, user_id: str, chunks_file: Path) -> None:
        payload = json.loads(chunks_file.read_text(encoding="utf-8"))
        created_at = _now_iso()
        batch_ids: List[str] = []
        batch_texts: List[str] = []
        batch_metadatas: List[Dict[str, str]] = []

        for idx, item in enumerate(payload):
            batch_ids.append(f"{document_id}_chunk_{idx}")
            batch_texts.append(item["text"])
            metadata: Dict[str, str] = dict(item["metadata"])
            metadata.update(
                {
                    "user_id": user_id,
                    "document_id": document_id,
                    "created_at": created_at,
                }
            )
            batch_metadatas.append(metadata)

        for start in range(0, len(batch_texts), self.batch_size):
            end = start + self.batch_size
            texts = batch_texts[start:end]
            ids = batch_ids[start:end]
            metadatas = batch_metadatas[start:end]

            batch_start = time.perf_counter()
            embeddings = self._create_embeddings(texts)
            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )
            self._log_batch(document_id, user_id, ids, metadatas)
            self.logger.info(
                "Embedded chunk batch",
                extra={
                    "document_id": document_id,
                    "user_id": user_id,
                    "batch_size": len(texts),
                    "duration_ms": round((time.perf_counter() - batch_start) * 1000, 2),
                },
            )

    def delete_document_vectors(self, document_id: str, user_id: str) -> None:
        try:
            self.collection.delete(
                where={
                    "$and": [
                        {"document_id": {"$eq": document_id}},
                        {"user_id": {"$eq": user_id}},
                    ]
                }
            )
            self.logger.info("Deleted document vectors", extra={"document_id": document_id, "user_id": user_id})
        except Exception as e:
            self.logger.warning(
                "Failed to delete document vectors (may not exist)",
                extra={"document_id": document_id, "user_id": user_id, "error": str(e)},
            )

    def _log_batch(self, document_id: str, user_id: str, ids: List[str], metadatas: List[Dict[str, str]]) -> None:
        if not self.log_dir:
            return
        log_path = Path(self.log_dir) / f"{document_id}.log"
        entry = {
            "document_id": document_id,
            "user_id": user_id,
            "ids": ids,
            "metadatas": metadatas,
            "timestamp": _now_iso(),
        }
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        start = time.perf_counter()
        if self.provider == "gemini":
            if self._gemini_client is None:  # pragma: no cover
                self._init_gemini()
            model_name = self.settings.gemini_embedding_model or "text-embedding-004"
            response = self._gemini_client.models.embed_content(
                model=model_name,
                contents=texts,
            )
            embeddings: List[List[float]] = []
            for embedding in response.embeddings:
                embeddings.append(list(embedding.values))
            self.logger.debug(
                "Generated Gemini embeddings",
                extra={"model": model_name, "batch": len(texts), "duration_ms": round((time.perf_counter() - start) * 1000, 2)},
            )
            return embeddings
        response = self._client().embeddings.create(
            model=self.settings.embedding_model_openai or "text-embedding-3-large",
            input=texts,
        )
        duration = time.perf_counter() - start
        self.logger.debug(
            "Generated OpenAI embeddings",
            extra={
                "model": self.settings.embedding_model_openai,
                "batch": len(texts),
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return [item.embedding for item in response.data]

