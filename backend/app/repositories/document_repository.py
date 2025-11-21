from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from supabase import Client
except ImportError:  # pragma: no cover
    Client = Any  # type: ignore

from ..core.config import Settings
from ..core.supabase_client import get_supabase_client
from ..models.document import Document, DocumentSource, DocumentStatus


class DocumentRepository(ABC):
    @abstractmethod
    def create(self, document: Document) -> Document: ...

    @abstractmethod
    def update(self, document_id: str, **fields) -> Optional[Document]: ...

    @abstractmethod
    def get(self, document_id: str) -> Optional[Document]: ...

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[Document]: ...

    @abstractmethod
    def mark_status(self, document_id: str, status: DocumentStatus, error_message: str | None = None) -> Optional[Document]: ...

    @abstractmethod
    def delete(self, document_id: str) -> None: ...


class LocalDocumentRepository(DocumentRepository):
    """JSON-file repository used for local dev and tests."""

    def __init__(self, store_path: Path):
        self._store_path = store_path
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._store_path.exists():
            self._store_path.write_text("{}", encoding="utf-8")

    def _load(self) -> Dict[str, Dict]:
        return json.loads(self._store_path.read_text(encoding="utf-8"))

    def _save(self, data: Dict[str, Dict]) -> None:
        self._store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create(self, document: Document) -> Document:
        data = self._load()
        data[document.id] = self._serialize(document)
        self._save(data)
        return document

    def update(self, document_id: str, **fields) -> Optional[Document]:
        data = self._load()
        if document_id not in data:
            return None
        data[document_id].update(fields)
        self._save(data)
        return Document(**data[document_id])

    def get(self, document_id: str) -> Optional[Document]:
        data = self._load()
        entry = data.get(document_id)
        return Document(**entry) if entry else None

    def list_by_user(self, user_id: str) -> List[Document]:
        data = self._load()
        return [Document(**doc) for doc in data.values() if doc["user_id"] == user_id]

    def mark_status(self, document_id: str, status: DocumentStatus, error_message: str | None = None) -> Optional[Document]:
        return self.update(document_id, status=status.value, error_message=error_message)

    def delete(self, document_id: str) -> None:
        data = self._load()
        if document_id in data:
            data.pop(document_id)
            self._save(data)

    def _serialize(self, document: Document) -> Dict:
        payload = document.model_dump()
        if document.storage_path:
            payload["storage_path"] = str(document.storage_path)
        return payload


class SupabaseDocumentRepository(DocumentRepository):
    def __init__(self, client: Client, table: str = "documents"):
        self.client = client
        self.table = table

    def create(self, document: Document) -> Document:
        payload = self._serialize(document)
        self.client.table(self.table).insert(payload).execute()
        return document

    def update(self, document_id: str, **fields) -> Optional[Document]:
        response = (
            self.client.table(self.table)
            .update(fields)
            .eq("id", document_id)
            .execute()
        )
        return self._row_to_document(response.data[0]) if response.data else None

    def get(self, document_id: str) -> Optional[Document]:
        response = (
            self.client.table(self.table)
            .select("*")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )
        return self._row_to_document(response.data[0]) if response.data else None

    def list_by_user(self, user_id: str) -> List[Document]:
        response = self.client.table(self.table).select("*").eq("user_id", user_id).execute()
        return [self._row_to_document(row) for row in response.data]

    def mark_status(self, document_id: str, status: DocumentStatus, error_message: str | None = None) -> Optional[Document]:
        payload = {"status": status.value, "error_message": error_message}
        return self.update(document_id, **payload)

    def delete(self, document_id: str) -> None:
        self.client.table(self.table).delete().eq("id", document_id).execute()

    def _serialize(self, document: Document) -> Dict:
        payload = document.model_dump()
        payload["source_type"] = document.source_type.value
        payload["status"] = document.status.value
        if document.storage_path:
            payload["storage_path"] = str(document.storage_path)
        if isinstance(document.source_value, Path):
            payload["source_value"] = str(document.source_value)
        return payload

    def _row_to_document(self, row: Dict) -> Document:
        storage_path = row.get("storage_path")
        return Document(
            id=row["id"],
            user_id=row["user_id"],
            source_type=DocumentSource(row["source_type"]),
            source_value=row["source_value"],
            storage_path=Path(storage_path) if storage_path else None,
            title=row.get("title"),
            status=DocumentStatus(row.get("status", DocumentStatus.uploading.value)),
            error_message=row.get("error_message"),
            created_at=row.get("created_at") or "",
            updated_at=row.get("updated_at") or "",
        )


def create_document_repository(settings: Settings) -> DocumentRepository:
    if settings.supabase_url and settings.supabase_anon_key:
        client = get_supabase_client()
        return SupabaseDocumentRepository(client)
    store_path = settings.storage_base_path.parent / "documents.json"
    return LocalDocumentRepository(store_path=store_path)

