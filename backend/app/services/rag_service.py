from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import chromadb
from openai import OpenAI

try:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None  # type: ignore

from ..core.config import get_settings
from ..logging_utils import bind_document_context
from .cache_service import CacheService, analysis_cache_key, chunks_cache_key, qa_cache_key


class RAGService:
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
        if chroma_client:
            self.chroma = chroma_client
        else:
            settings = get_settings()
            if settings.chroma_server_host:
                self.chroma = chromadb.HttpClient(
                    host=settings.chroma_server_host,
                    port=settings.chroma_server_port,
                    ssl=settings.chroma_server_ssl,
                    headers={"Authorization": f"Bearer {settings.chroma_server_api_key}"} if settings.chroma_server_api_key else None,
                )
            elif settings.chroma_persist_directory:
                from pathlib import Path
                persist_dir = Path(settings.chroma_persist_directory)
                persist_dir.mkdir(parents=True, exist_ok=True)
                from chromadb.config import Settings as ChromaSettings
                chroma_settings = ChromaSettings(
                    persist_directory=str(persist_dir),
                    anonymized_telemetry=False,
                )
                self.chroma = chromadb.PersistentClient(path=str(persist_dir), settings=chroma_settings)
            else:
                from chromadb.config import Settings as ChromaSettings
                self.chroma = chromadb.Client(settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self.chroma.get_or_create_collection("documents")
        self.provider = (self.settings.llm_provider or "openai").lower()
        self.embedding_provider = (self.settings.embedding_provider or "openai").lower()
        need_openai = self.provider == "openai" or self.embedding_provider == "openai"
        self.openai = openai_client if openai_client is not None else (OpenAI() if need_openai else None)
        self._gemini_client: Optional["genai.Client"] = None  # type: ignore
        if (self.provider == "gemini" or self.embedding_provider == "gemini"):
            self._init_gemini()
        if self.provider == "gemini":
            self.model_map = {
                "mini": self.settings.gemini_model_flash,
                "turbo": self.settings.gemini_model_pro,
            }
        else:
            self.model_map = {
                "mini": self.settings.openai_model_mini,
                "turbo": self.settings.openai_model_turbo,
            }
        self.cache = cache or CacheService(redis_client=redis_client)
        self.logger = logging.getLogger("app.services.rag")

    # --- Public API -----------------------------------------------------

    def get_analysis(self, document_id: str) -> Optional[Dict[str, Any]]:
        cache_key = analysis_cache_key(document_id)
        return self._cache_get_json(cache_key, layer="analysis")

    def query(
        self,
        question: str,
        document_id: str,
        user_id: str,
        model: str = "mini",
        temperature: Optional[float] = None,
        k: int = 10,
    ) -> Dict[str, Any]:
        bind_document_context(document_id)
        cache_key = qa_cache_key(document_id, question)
        cached = self._cache_get_json(cache_key, layer="qa")
        if cached:
            self.logger.info(
                "QA cache hit",
                extra={"document_id": document_id, "user_id": user_id},
            )
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
        self.logger.info(
            "Generated answer",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "model": answer_payload["model_used"],
                "chunks_used": len(reranked[:5]),
            },
        )
        self._cache_set_json(cache_key, response_payload, self.CACHE_TTL, layer="qa")
        return {**response_payload, "cached": False}

    def get_relevant_chunks(
        self,
        question: str,
        document_id: Optional[str],
        user_id: str,
        k: int = 10,
    ) -> List[Dict]:
        # Only bind document context if we have a specific document
        if document_id:
            bind_document_context(document_id)
        
        cache_key = chunks_cache_key(document_id or "all_docs", question)
        cached_chunks = self._cache_get_json(cache_key, layer="chunks")
        if cached_chunks:
            self.logger.debug(
                "Chunk cache hit",
                extra={"document_id": document_id or "all", "user_id": user_id, "results": len(cached_chunks)},
            )
            return cached_chunks

        embedding = self._embed_question(question)
        start = time.perf_counter()
        
        # Build where clause - filter by user_id, optionally by document_id
        where_conditions = [{"user_id": {"$eq": user_id}}]
        if document_id:
            where_conditions.append({"document_id": {"$eq": document_id}})
        
        where_clause = {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]
        
        results = self.collection.query(
            query_embeddings=[embedding],
            where=where_clause,
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

        duration = time.perf_counter() - start
        self.logger.info(
            "Vector search completed",
            extra={
                "document_id": document_id or "all",
                "user_id": user_id,
                "results": len(chunks),
                "duration_ms": round(duration * 1000, 2),
            },
        )
        self._cache_set_json(cache_key, chunks, ttl=60 * 60, layer="chunks")
        return chunks

    def rerank_chunks(self, question: str, chunks: List[Dict]) -> List[Dict]:
        section_groups: Dict[str, List[Dict]] = {}
        for chunk in chunks:
            section = chunk["metadata"].get("section_path", "unknown")
            section_groups.setdefault(section, []).append(chunk)

        scores: List[tuple[str, float]] = []
        # Core sections that should be prioritized
        CORE_SECTIONS = ["Abstract", "Introduction", "Conclusion", "摘要", "引言", "结论"]

        for section, section_chunks in section_groups.items():
            # 1. Base score from average distance
            avg_distance = sum(c["distance"] for c in section_chunks) / len(section_chunks)
            score = avg_distance

            # 2. Boost core sections by 30% (lower distance = higher rank)
            if any(core in section for core in CORE_SECTIONS):
                score *= 0.7

            # 3. Only boost tables if question explicitly asks about them
            has_table = any(c["metadata"].get("element_type") == "table" for c in section_chunks)
            if "表格" in question or "table" in question.lower():
                if has_table:
                    score *= 0.8

            scores.append((section, score))

        scores.sort(key=lambda item: item[1])

        reranked: List[Dict] = []
        for section, _ in scores:
            section_chunks = sorted(section_groups[section], key=lambda c: int(c["metadata"].get("chunk_index", 0)))
            reranked.extend(section_chunks)

        return reranked

    def build_context(self, chunks: List[Dict], max_tokens: int = 20000) -> str:
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
        model_key = model if model in self.model_map else "mini"
        model_name = self.model_map[model_key]
        temp = temperature if temperature is not None else self.MODEL_TEMPERATURE[model_key]

        prompt = (
            "你是比特币白皮书专家。请仔细阅读上下文，提取关键信息回答问题。\n\n"
            "规则：\n"
            "- 答案一定在上下文中，请仔细寻找\n"
            "- 用中文简洁回答，2-3句话即可\n"
            "- 直接给出答案，不要说'根据上下文'等废话\n"
            "- 绝对禁止说'找不到'、'无法回答'、'抱歉'\n\n"
            f"上下文：\n{context}\n\n"
            f"问题：{question}\n\n"
            "答案："
        )

        start = time.perf_counter()
        if self.provider == "gemini":
            if self._gemini_client is None:  # pragma: no cover
                self._init_gemini()
            response = self._gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,  # v1 SDK expects string directly
                config=genai_types.GenerateContentConfig(
                    temperature=temp,
                    max_output_tokens=800,
                ),
            )
            # Safely extract text from response
            content = ""
            if hasattr(response, "text") and response.text:
                content = response.text
            elif response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    if hasattr(candidate.content, "parts") and candidate.content.parts:
                        if len(candidate.content.parts) > 0:
                            content = candidate.content.parts[0].text
            
            if not content:
                content = self.FALLBACK_ANSWER
            self.logger.info(
                "Gemini completion finished",
                extra={"model": model_name, "duration_ms": round((time.perf_counter() - start) * 1000, 2)},
            )
            return {"answer": content, "model_used": model_name}
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
        self.logger.info(
            "OpenAI completion finished",
            extra={"model": model_name, "duration_ms": round((time.perf_counter() - start) * 1000, 2)},
        )
        return {"answer": content, "model_used": model_name}

    def _embed_question(self, question: str) -> List[float]:
        start = time.perf_counter()
        if self.embedding_provider == "gemini":
            if self._gemini_client is None:  # pragma: no cover
                self._init_gemini()
            response = self._gemini_client.models.embed_content(
                model=self.settings.gemini_embedding_model or "text-embedding-004",
                contents=[question],
            )
            if response.embeddings:
                self.logger.debug(
                    "Gemini embedding generated",
                    extra={"model": self.settings.gemini_embedding_model, "duration_ms": round((time.perf_counter() - start) * 1000, 2)},
                )
                return list(response.embeddings[0].values)
            return []
        response = self.openai.embeddings.create(
            model=self.settings.embedding_model_openai or "text-embedding-3-large",
            input=question,
        )
        embedding = response.data[0].embedding
        self.logger.debug(
            "OpenAI embedding generated",
            extra={
                "model": self.settings.embedding_model_openai,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return embedding

    def _cache_get_json(self, key: str, layer: Optional[str] = None) -> Optional[Any]:
        return self.cache.get_json(key, layer=layer)

    def _cache_set_json(self, key: str, payload: Any, ttl: int, layer: Optional[str] = None) -> None:
        self.cache.set_json(key, payload, ttl, layer=layer)

    def _init_gemini(self) -> None:
        if genai is None:  # pragma: no cover
            raise RuntimeError("google-genai is not installed. Run `pip install google-genai`.")
        if not self.settings.google_api_key:
            raise RuntimeError("Missing Google API key for Gemini models.")
        self._gemini_client = genai.Client(api_key=self.settings.google_api_key)

