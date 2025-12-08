import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache_service import CacheService
from app.services.rag_service import RAGService
from .test_cache_service import FakeRedis  # reuse stub


def test_query_returns_fallback_and_caches(monkeypatch):
    cache = CacheService(redis_client=FakeRedis())
    service = RAGService(cache=cache)

    def fake_get_relevant_chunks(*args, **kwargs):
        return []

    service.get_relevant_chunks = fake_get_relevant_chunks  # type: ignore

    result_first = service.query(
        question="项目的共识机制是什么？",
        document_id="doc-1",
        user_id="user-1",
    )
    assert result_first["answer"] == service.FALLBACK_ANSWER
    assert result_first["sources"] == []
    assert result_first["model_used"] is None
    assert result_first["cached"] is False

    result_cached = service.query(
        question="项目的共识机制是什么？",
        document_id="doc-1",
        user_id="user-1",
    )
    assert result_cached["cached"] is True
    assert result_cached["answer"] == service.FALLBACK_ANSWER


