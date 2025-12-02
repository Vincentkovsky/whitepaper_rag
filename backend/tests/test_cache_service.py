import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time

from app.services.cache_service import (
    CacheService,
    qa_cache_key,
    chunks_cache_key,
    analysis_cache_key,
)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def setex(self, key, ttl, value):
        expires_at = time.time() + ttl
        self.store[key] = (value, expires_at)

    def get(self, key):
        entry = self.store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at < time.time():
            self.store.pop(key, None)
            return None
        return value

    def delete(self, key):
        self.store.pop(key, None)


def test_cache_service_set_and_get():
    cache = CacheService(redis_client=FakeRedis())
    key = qa_cache_key("doc", "question")
    cache.set(key, "result", ttl=1)
    assert cache.get(key, layer="qa") == "result"
    assert cache.metrics["qa"]["hit"] == 1

    cache.set_json(chunks_cache_key("doc", "q"), {"foo": "bar"}, ttl=1)
    assert cache.get_json(chunks_cache_key("doc", "q"), layer="chunks") == {"foo": "bar"}
    assert cache.metrics["chunks"]["hit"] == 1


def test_cache_service_expiry():
    cache = CacheService(redis_client=FakeRedis())
    key = analysis_cache_key("doc")
    cache.set(key, "value", ttl=0)
    time.sleep(0.01)
    assert cache.get(key, layer="analysis") is None
    assert cache.metrics["analysis"]["miss"] >= 1

