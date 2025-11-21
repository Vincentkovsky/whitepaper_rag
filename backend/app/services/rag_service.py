from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import chromadb
from openai import OpenAI

from ..core.config import get_settings
from .cache_service import CacheService, qa_cache_key, chunks_cache_key


class RAGService:
    MODEL_MAP = {
        "mini": "gpt-4o-mini",
        "turbo": "gpt-4-turbo",
    }
    MODEL_TEMPERATURE = {
        "mini": 0.2,
        "turbo": 0.3,
    }
    CACHE_TTL = 60 * 60  # 1 hour
    FALLBACK_ANSWER = "抱歉，我在文档中没有找到足够的信息来回答这个问题。"

    def __init__(
        self,
        chroma_client: Optional[chromadb.Client] = None,
        cache: Optional[CacheService] = None,
        redis_client=None,
        openai_client: Optional[OpenAI] = None,
    ):
        self.settings = get_settings()
        self.chroma = chroma_client or chromadb.Client()
        self.collection = self.chroma.get_or_create_collection("documents")
        self.openai = openai_client or OpenAI()
        self.cache = cache or CacheService(redis_client=redis_client)

    # --- Public API -----------------------------------------------------

    def query(
        self,
        question: str,
        document_id: str,
        user_id: str,
        model: str = "mini",
        temperature: Optional[float] = None,
        k: int = 10,
    ) -> Dict[str, Any]:
        cache_key = qa_cache_key(document_id, question)
        cached = self._cache_get_json(cache_key, layer="qa")
        if cached:
            return {**cached, "cached": True}

        chunks = self.get_relevant_chunks(
            question=question, document_id=document_id, user_id=user_id, k=k
        )
        if not chunks:
            fallback_payload = {
                "answer": self.FALLBACK_ANSWER,
                "sources": [],
                "model_used": None,
            }
            self._cache_set_json(cache_key, fallback_payload, self.CACHE_TTL, layer="qa")
            return {**fallback_payload, "cached": False}

        reranked = self.rerank_chunks(question, chunks)
        context = self.build_context(reranked[:5])
        if not context.strip():
            fallback_payload = {
                "answer": self.FALLBACK_ANSWER,
                "sources": [],
                "model_used": None,
            }
            self._cache_set_json(cache_key, fallback_payload, self.CACHE_TTL, layer="qa")
            return {**fallback_payload, "cached": False}

        answer_payload = self._generate_answer(
            question=question,
            context=context,
            model=model,
            temperature=temperature,
        )

        sources = self._build_sources(reranked[:3])
        response_payload = {
            "answer": answer_payload["answer"],
            "sources": sources,
            "model_used": answer_payload["model_used"],
        }
        self._cache_set_json(cache_key, response_payload, self.CACHE_TTL, layer="qa")
        return {**response_payload, "cached": False}

    def get_relevant_chunks(
        self,
        question: str,
        document_id: str,
        user_id: str,
        k: int = 10,
    ) -> List[Dict]:
        cache_key = chunks_cache_key(document_id, question)
        cached_chunks = self._cache_get_json(cache_key, layer="chunks")
        if cached_chunks:
            return cached_chunks

        embedding = self._embed_question(question)
        results = self.collection.query(
            query_embeddings=[embedding],
            where={
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$eq": document_id}},
                ]
            },
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        chunks: List[Dict] = []
        for idx in range(len(results["documents"][0])):
            chunks.append(
                {
                    "id": results["ids"][0][idx],
                    "text": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx],
                    "distance": results["distances"][0][idx],
                }
            )

        self._cache_set_json(cache_key, chunks, ttl=60 * 60, layer="chunks")
        return chunks

    def rerank_chunks(self, question: str, chunks: List[Dict]) -> List[Dict]:
        section_groups: Dict[str, List[Dict]] = {}
        for chunk in chunks:
            section = chunk["metadata"].get("section_path", "unknown")
            section_groups.setdefault(section, []).append(chunk)

        scores: List[tuple[str, float]] = []
        for section, section_chunks in section_groups.items():
            avg_distance = sum(c["distance"] for c in section_chunks) / len(section_chunks)
            has_table = any(c["metadata"].get("element_type") == "table" for c in section_chunks)
            score = avg_distance * (0.9 if has_table else 1.0)
            scores.append((section, score))

        scores.sort(key=lambda item: item[1])

        reranked: List[Dict] = []
        for section, _ in scores:
            section_chunks = sorted(section_groups[section], key=lambda c: int(c["metadata"].get("chunk_index", 0)))
            reranked.extend(section_chunks)

        return reranked

    def build_context(self, chunks: List[Dict], max_tokens: int = 2000) -> str:
        context_parts: List[str] = []
        total = 0
        for chunk in chunks:
            section_path = chunk["metadata"].get("section_path", "unknown")
            chunk_text = f"[来源: {section_path}]\n{chunk['text']}\n"
            chunk_len = len(chunk_text)
            if total + chunk_len > max_tokens:
                break
            context_parts.append(chunk_text)
            total += chunk_len
        return "\n---\n\n".join(context_parts)

    # --- Internal utilities --------------------------------------------

    def _build_sources(self, chunks: List[Dict]) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            snippet = chunk.get("text", "")
            sources.append(
                {
                    "section": metadata.get("section_path"),
                    "page": metadata.get("page_number"),
                    "text": snippet[:200] + ("..." if len(snippet) > 200 else ""),
                }
            )
        return sources

    def _generate_answer(
        self,
        question: str,
        context: str,
        model: str,
        temperature: Optional[float],
    ) -> Dict[str, Any]:
        model_key = model if model in self.MODEL_MAP else "mini"
        model_name = self.MODEL_MAP[model_key]
        temp = temperature if temperature is not None else self.MODEL_TEMPERATURE[model_key]

        prompt = (
            "你是一名专业的区块链白皮书分析助手。"
            "请仅根据提供的上下文回答用户的问题，无法回答时明确说明。"
            "\n\n上下文:\n"
            f"{context}\n\n"
            f"问题: {question}\n\n回答:"
        )

        response = self.openai.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Answer in Chinese and cite facts from context only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=temp,
        )
        content = response.choices[0].message.content
        return {"answer": content, "model_used": model_name}

    def _embed_question(self, question: str) -> List[float]:
        response = self.openai.embeddings.create(
            model="text-embedding-3-large",
            input=question,
        )
        return response.data[0].embedding

    def _cache_get_json(self, key: str, layer: Optional[str] = None) -> Optional[Any]:
        return self.cache.get_json(key, layer=layer)

    def _cache_set_json(self, key: str, payload: Any, ttl: int, layer: Optional[str] = None) -> None:
        self.cache.set_json(key, payload, ttl, layer=layer)

