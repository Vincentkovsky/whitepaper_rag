from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentStatus(str, Enum):
    uploading = "uploading"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"


class DocumentSource(str, Enum):
    pdf = "pdf"
    url = "url"
    text = "text"


class Document(BaseModel):
    id: str
    user_id: str
    source_type: DocumentSource
    source_value: str
    storage_path: Optional[Path] = None
    title: Optional[str] = None
    status: DocumentStatus = DocumentStatus.uploading
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class DocumentListItem(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    source_value: str
    status: DocumentStatus
    created_at: str
