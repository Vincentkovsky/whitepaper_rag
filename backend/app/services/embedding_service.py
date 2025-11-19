from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from openai import OpenAI

from ..core.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.chroma = chromadb.Client()
        self.collection = self.chroma.get_or_create_collection("documents")
        self._openai_client: Optional[OpenAI] = None

    def _client(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI()
        return self._openai_client

    def embed_chunks(self, document_id: str, user_id: str, chunks_file: Path) -> None:
        payload = json.loads(chunks_file.read_text(encoding="utf-8"))
        batch_texts = [item["text"] for item in payload]

        response = self._client().embeddings.create(
            model="text-embedding-3-small",
            input=batch_texts,
        )

        embeddings = [item.embedding for item in response.data]
        metadatas = []
        ids: List[str] = []
        created_at = _now_iso()

        for idx, item in enumerate(payload):
            metadata: Dict[str, str] = dict(item["metadata"])
            metadata.update(
                {
                    "user_id": user_id,
                    "document_id": document_id,
                    "created_at": created_at,
                }
            )
            metadatas.append(metadata)
            ids.append(f"{document_id}_chunk_{idx}")

        self.collection.add(
            documents=batch_texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def delete_document_vectors(self, document_id: str, user_id: str) -> None:
        self.collection.delete(
            where={
                "document_id": {"$eq": document_id},
                "user_id": {"$eq": user_id},
            }
        )

