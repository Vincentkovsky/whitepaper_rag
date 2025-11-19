from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


def qa_cache_key(document_id: str, question: str) -> str:
    signature = hashlib.md5(f"{document_id}:{question}".encode("utf-8")).hexdigest()
    return f"qa:{signature}"


def chunks_cache_key(document_id: str, question: str) -> str:
    signature = hashlib.md5(f"chunks:{document_id}:{question}".encode("utf-8")).hexdigest()
    return f"chunks:{signature}"


def analysis_cache_key(document_id: str) -> str:
    return f"analysis:{document_id}"


@dataclass
class CacheEntry:
    value: str
    expires_at: float


class CacheService:
    """
    Lightweight in-memory cache with TTL semantics.

    In production this should be replaced with Redis, but keeping the interface identical
    allows us to swap implementations later without touching business logic.
    """

    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str, ttl: int) -> None:
        expires_at = time.time() + ttl
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expires_at < time.time():
                self._store.pop(key, None)
                return None
            return entry.value

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, payload: Dict[str, Any], ttl: int) -> None:
        self.set(key, json.dumps(payload), ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

