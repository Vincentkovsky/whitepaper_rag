from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

try:
    from redis import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore

from ..core.config import get_settings


def qa_cache_key(document_id: str, question: str) -> str:
    signature = hashlib.md5(f"{document_id}:{question}".encode("utf-8")).hexdigest()
    return f"qa:{signature}"


def chunks_cache_key(document_id: str, question: str) -> str:
    signature = hashlib.md5(f"chunks:{document_id}:{question}".encode("utf-8")).hexdigest()
    return f"chunks:{signature}"


def analysis_cache_key(document_id: str) -> str:
    return f"analysis:{document_id}"


class CacheService:
    """Redis-backed cache service with simple hit/miss metrics."""

    DEFAULT_LAYERS = ["qa", "chunks", "analysis"]

    def __init__(self, redis_client: Optional[Redis] = None, metric_layers: Optional[list[str]] = None):
        if redis_client is not None:
            self.redis = redis_client
        else:
            if Redis is None:  # pragma: no cover
                raise RuntimeError("redis package is required for CacheService")
            settings = get_settings()
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        layers = metric_layers or self.DEFAULT_LAYERS
        self.metrics: Dict[str, Dict[str, int]] = {layer: {"hit": 0, "miss": 0} for layer in layers}

    def set(self, key: str, value: str, ttl: int, layer: Optional[str] = None) -> None:
        self.redis.setex(key, ttl, value)

    def get(self, key: str, layer: Optional[str] = None) -> Optional[str]:
        value = self.redis.get(key)
        if value is not None:
            self._record_hit(layer)
            return value
        self._record_miss(layer)
        return None

    def get_json(self, key: str, layer: Optional[str] = None) -> Optional[Any]:
        raw = self.get(key, layer=layer)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, payload: Any, ttl: int, layer: Optional[str] = None) -> None:
        self.set(key, json.dumps(payload, ensure_ascii=False), ttl, layer=layer)

    def delete(self, key: str) -> None:
        self.redis.delete(key)

    # --- Metrics helpers -------------------------------------------------
    def _record_hit(self, layer: Optional[str]) -> None:
        if layer and layer in self.metrics:
            self.metrics[layer]["hit"] += 1

    def _record_miss(self, layer: Optional[str]) -> None:
        if layer and layer in self.metrics:
            self.metrics[layer]["miss"] += 1
