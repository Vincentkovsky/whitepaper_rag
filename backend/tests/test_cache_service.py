import time

from backend.app.services.cache_service import (
    CacheService,
    qa_cache_key,
    chunks_cache_key,
    analysis_cache_key,
)


def test_cache_service_set_and_get():
    cache = CacheService()
    key = qa_cache_key("doc", "question")
    cache.set(key, "result", ttl=1)
    assert cache.get(key) == "result"

    cache.set_json(chunks_cache_key("doc", "q"), {"foo": "bar"}, ttl=1)
    assert cache.get_json(chunks_cache_key("doc", "q")) == {"foo": "bar"}


def test_cache_service_expiry():
    cache = CacheService()
    key = analysis_cache_key("doc")
    cache.set(key, "value", ttl=0)
    time.sleep(0.01)
    assert cache.get(key) is None

