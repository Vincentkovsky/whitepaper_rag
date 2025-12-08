from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import time

import httpx
import asyncio
from openai import OpenAI

try:
    from celery import Celery, Task
except ImportError:  # pragma: no cover
    Celery = None
    Task = Any  # type: ignore

from ..core.config import get_settings
from ..core.database import AsyncSessionLocal
from ..logging_utils import bind_document_context, bind_task_context, clear_context
from ..models.document import DocumentSource, DocumentStatus
from ..repositories.document_repository import PostgresDocumentRepository
from ..services.chunking_service import StructuredChunker
from ..services.embedding_service import EmbeddingService
from ..services.rag_service import RAGService
from ..services.cache_service import analysis_cache_key
from ..services.subscription_service import get_subscription_service
from ..telemetry.task_metrics import (
    record_task_completed,
    record_task_enqueued,
    record_task_failed,
    record_task_started,
)
from .priority import TaskPriority, get_task_route

settings = get_settings()
celery_app = (
    Celery(
        "blockchain_rag",
        broker=settings.celery_broker_url,
        backend=settings.redis_url,
    )
    if Celery
    else None
)

logger = logging.getLogger(__name__)

ANALYSIS_CACHE_TTL = 60 * 60 * 24  # 24h
DEFAULT_PARSE_SKU = "document_upload_pdf"
ANALYSIS_SKU = "analysis_report"
TASK_SLA_SECONDS = {
    "documents.parse": 600,
    "analysis.generate": 900,
}


def get_document_repository() -> PostgresDocumentRepository:
    """Get async document repository with new session"""
    session = AsyncSessionLocal()
    return PostgresDocumentRepository(session)


@lru_cache(maxsize=1)
def get_chunker() -> StructuredChunker:
    return StructuredChunker()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingService:
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)
    return OpenAI()


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    return RAGService(openai_client=get_openai_client())


def _refund_on_failure(user_id: str, sku: str, reason: str) -> None:
    try:
        get_subscription_service().refund_credits(user_id, sku, reason=reason)
    except Exception:  # pragma: no cover
        logger.exception("Failed to refund credits", extra={"user_id": user_id, "sku": sku})


def _check_sla(task_name: str, duration: float, success: bool = True) -> None:
    threshold = TASK_SLA_SECONDS.get(task_name)
    if not threshold:
        return
    if duration > threshold:
        logger.warning(
            "Task SLA breached",
            extra={
                "task_name": task_name,
                "duration": duration,
                "threshold": threshold,
                "success": success,
            },
        )


async def _parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    sku: str = DEFAULT_PARSE_SKU,
    task: Optional[Task] = None,
) -> None:
    bind_document_context(document_id)
    if task is not None:
        bind_task_context(getattr(getattr(task, "request", None), "id", None))
    repo = get_document_repository()
    _update_task_progress(task, 0, "开始解析")
    logger.info("Starting parse_document_task", extra={"document_id": document_id})
    record_task_started("documents.parse")
    start_time = time.perf_counter()

    try:
        document = await repo.get(document_id)
        if not document:
            logger.error("Document not found", extra={"document_id": document_id})
            raise ValueError("Document not found")

        await repo.mark_status(document_id, DocumentStatus.parsing)

        try:
            loop = asyncio.get_running_loop()
            
            # Run CPU-bound/Sync-IO tasks in thread pool
            elements = await loop.run_in_executor(
                None, _extract_elements, document.source_type, document, source_url
            )
            _update_task_progress(task, 30, "已提取元素")

            # Try to extract title from elements
            title = None
            for element in elements:
                if element.get("category") == "Title":
                    title = element.get("text", "").strip()
                    if title:
                        break
            
            if title:
                await repo.update_title(document_id, title)

            chunker = get_chunker()
            sections = await loop.run_in_executor(None, chunker.build_sections, elements)
            chunks = await loop.run_in_executor(None, chunker.chunk_sections, sections)
            _update_task_progress(task, 50, "已完成分块")

            chunks_path = _chunks_path(document_id)
            await loop.run_in_executor(None, chunker.serialize_chunks, chunks, chunks_path)
            _update_task_progress(task, 70, "已生成 chunk 文件")

            embedder = get_embedder()
            await loop.run_in_executor(
                None,
                embedder.embed_chunks,
                document_id,
                user_id,
                chunks_path,
            )
            _update_task_progress(task, 90, "向量入库完成")

            await repo.mark_status(document_id, DocumentStatus.completed)
            _update_task_progress(task, 100, "解析完成")
            logger.info("Completed parse_document_task", extra={"document_id": document_id})
            duration = time.perf_counter() - start_time
            record_task_completed("documents.parse", duration)
            _check_sla("documents.parse", duration)
        except Exception as exc:
            logger.exception("Failed to parse document", extra={"document_id": document_id})
            await repo.mark_status(document_id, DocumentStatus.failed, str(exc))
            _update_task_progress(task, 100, "解析失败")
            _refund_on_failure(user_id, sku, str(exc))
            duration = time.perf_counter() - start_time
            record_task_failed("documents.parse", duration, str(exc))
            _check_sla("documents.parse", duration, success=False)
            setattr(exc, "credits_refunded", True)
            raise
    finally:
        await repo.session.close()
        clear_context()


import trafilatura

# ... (imports)

def _extract_elements(source_type: DocumentSource, document, source_url: Optional[str]) -> list[Dict]:
    chunker = get_chunker()
    if source_type == DocumentSource.pdf:
        if not document.storage_path:
            raise ValueError("PDF document missing storage_path")
        return chunker.parse_pdf(Path(document.storage_path))
    if source_type == DocumentSource.url:
        url = source_url or document.source_value
        html = _fetch_remote_content(url)
        text = trafilatura.extract(html, include_comments=False, include_tables=True, no_fallback=True, output_format="markdown")
        if not text:
            # Fallback to unstructured parsing if trafilatura fails to extract main content
            return chunker.parse_html(html)
        return chunker.parse_plain_text(text)
    return chunker.parse_plain_text(document.source_value)


from curl_cffi import requests

# ... (imports)




def _fetch_remote_content(url: str) -> str:
    """
    Use curl_cffi to simulate a real browser download and bypass TLS fingerprint detection.
    Also implements heuristic iframe extraction to find the real content.
    """
    try:
        # 1. Fetch the initial page
        response = requests.get(
            url,
            impersonate="chrome120", 
            headers={
                "Referer": "https://www.zhihu.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            },
            cookies={
                "d_c0": "AGD8-dummy-device-id" 
            },
            timeout=15
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Download failed with status {response.status_code}")

        html = response.text
        
        # 2. Parse with BeautifulSoup to check for iframes
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            soup = BeautifulSoup(html, 'html.parser')
            iframes = soup.find_all('iframe')
            
            if not iframes:
                return html
                
            # 3. Heuristic scoring for iframes
            best_iframe = None
            max_score = 0
            
            for iframe in iframes:
                src = iframe.get('src')
                if not src:
                    continue
                    
                score = 0
                
                # Heuristic 1: Size attributes
                width = iframe.get('width')
                height = iframe.get('height')
                style = iframe.get('style', '').lower()
                
                # Prefer large or full-screen iframes
                if width and (width == '100%' or (width.isdigit() and int(width) > 800)):
                    score += 2
                if height and (height == '100%' or (height.isdigit() and int(height) > 600)):
                    score += 2
                if 'width: 100%' in style or 'height: 100%' in style:
                    score += 2
                    
                # Heuristic 2: Keywords in URL
                src_lower = src.lower()
                if 'pdf' in src_lower:
                    score += 3
                if 'article' in src_lower or 'content' in src_lower:
                    score += 1
                if 'viewer' in src_lower:
                    score += 2
                    
                # Heuristic 3: ID/Class names
                id_attr = iframe.get('id', '').lower()
                class_attr = str(iframe.get('class', '')).lower()
                if 'content' in id_attr or 'main' in id_attr or 'article' in id_attr:
                    score += 2
                if 'content' in class_attr or 'main' in class_attr:
                    score += 2
                
                # Heuristic 4: Avoid common ad/tracking iframes
                if 'ads' in src_lower or 'tracker' in src_lower or 'analytics' in src_lower:
                    score -= 10
                if 'facebook' in src_lower or 'twitter' in src_lower or 'youtube' in src_lower:
                    score -= 5

                if score > max_score:
                    max_score = score
                    best_iframe = src

            # 4. If a good candidate is found (score > threshold), fetch it
            if best_iframe and max_score > 0:
                logger.info(f"Found content iframe with score {max_score}: {best_iframe}")
                full_url = urljoin(url, best_iframe)
                
                iframe_response = requests.get(
                    full_url,
                    impersonate="chrome120",
                    headers={
                        "Referer": url, # Set referer to the parent page
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    },
                    timeout=15
                )
                
                if iframe_response.status_code == 200:
                    return iframe_response.text
                    
        except ImportError:
            logger.warning("BeautifulSoup not installed, skipping iframe extraction")
        except Exception as e:
            logger.warning(f"Iframe extraction failed: {e}")

        return html

    except Exception as e:
        raise RuntimeError(f"Failed to fetch URL content: {url}. Error: {str(e)}")


def _chunks_path(document_id: str) -> Path:
    return settings.storage_base_path.parent / "chunks" / f"{document_id}.json"


def _update_task_progress(task: Optional[Task], progress: int, message: str) -> None:
    if not task:
        return
    try:
        task.update_state(state="PROGRESS", meta={"progress": progress, "message": message})
    except Exception:  # pragma: no cover
        logger.debug("Failed to update task progress", exc_info=True)


async def _execute_analysis_workflow(document_id: str, user_id: str) -> Dict:
    bind_document_context(document_id)
    repo = get_document_repository()
    try:
        document = await repo.get(document_id)
        if not document or document.user_id != user_id:
            raise ValueError("Document not found or access denied")
        record_task_started("analysis.generate")
        start_time = time.perf_counter()

        rag_service = get_rag_service()
        openai_client = get_openai_client()

        planner = make_generate_sub_queries(openai_client)
        retriever = make_retrieve_all_contexts(rag_service)
        analyze_fn = make_analyze_dimension(openai_client)
        analyzers = make_dimension_analyzers(analyze_fn)
        synthesizer = make_synthesize_final_report(openai_client)

        state: AnalysisState = {
            "document_id": document_id,
            "user_id": user_id,
            "dimensions": list(DEFAULT_DIMENSIONS),
            "sub_queries": {},
            "retrieved_contexts": {},
            "analysis_results": {},
        }

        try:
            loop = asyncio.get_running_loop()
            
            # Planner
            plan_update = await loop.run_in_executor(None, planner, state)
            state.update(plan_update)
            
            # Retriever
            retrieve_update = await loop.run_in_executor(None, retriever, state)
            state.update(retrieve_update)
            
            # Analyzers
            for key in ["analyze_tech", "analyze_econ", "analyze_team", "analyze_risk"]:
                result = await loop.run_in_executor(None, analyzers[key], state)
                state.update(result)
                
            # Synthesizer
            final = await loop.run_in_executor(None, synthesizer, state)
            
            if not final or "final_report" not in final:
                raise RuntimeError("Failed to synthesize analysis report")

            result = final["final_report"]
            rag_service.cache.set_json(
                analysis_cache_key(document_id),
                result,
                ttl=ANALYSIS_CACHE_TTL,
                layer="analysis",
            )
            duration = time.perf_counter() - start_time
            record_task_completed("analysis.generate", duration)
            _check_sla("analysis.generate", duration)
            return result
        except Exception as exc:
            duration = time.perf_counter() - start_time
            record_task_failed("analysis.generate", duration, str(exc))
            _check_sla("analysis.generate", duration, success=False)
            raise
    finally:
        await repo.session.close()
        clear_context()


def _dispatch_task(task_callable, task_name: str, priority: TaskPriority, *args, **kwargs):
    record_task_enqueued(task_name, priority.value)
    if celery_app and not settings.run_tasks_inline:
        route = get_task_route(priority)
        task_callable.apply_async(
            args=args,
            kwargs=kwargs,
            queue=route.queue,
            priority=route.priority,
            retry_policy=route.retry_policy,
        )
    else:
        task_callable(*args, **kwargs)


if celery_app:
    import asyncio

    @celery_app.task(name="documents.parse", bind=True)
    def parse_document_task(
        self: Task,
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            loop.create_task(_parse_document(document_id, user_id, source_url, sku=sku, task=self))
        else:
            asyncio.run(_parse_document(document_id, user_id, source_url, sku=sku, task=self))

    @celery_app.task(name="analysis.generate", bind=True)
    def generate_analysis_task(
        self: Task,
        document_id: str,
        user_id: str,
        sku: str = ANALYSIS_SKU,
    ) -> Dict:
        _update_task_progress(self, 0, "开始分析")
        try:
            bind_task_context(getattr(self.request, "id", None))
            
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop:
                # If we are in a loop (e.g. inline execution), we return the coroutine
                # The caller (enqueue_generate_analysis) must await it
                return _execute_analysis_workflow(document_id, user_id)
            else:
                report = asyncio.run(_execute_analysis_workflow(document_id, user_id))
                
            _update_task_progress(self, 100, "分析完成")
            return report
        except Exception as exc:
            _update_task_progress(self, 100, "分析失败")
            _refund_on_failure(user_id, sku, str(exc))
            raise

else:
    import asyncio

    def parse_document_task(
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            loop.create_task(_parse_document(document_id, user_id, source_url, sku=sku, task=None))
        else:
            asyncio.run(_parse_document(document_id, user_id, source_url, sku=sku, task=None))

    def generate_analysis_task(
        document_id: str,
        user_id: str,
        sku: str = ANALYSIS_SKU,
    ) -> Dict:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop:
                return _execute_analysis_workflow(document_id, user_id)
            else:
                return asyncio.run(_execute_analysis_workflow(document_id, user_id))
        except Exception as exc:
            _refund_on_failure(user_id, sku, str(exc))
            raise


def enqueue_parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    *,
    priority: TaskPriority = TaskPriority.STANDARD,
    sku: str = DEFAULT_PARSE_SKU,
) -> None:
    """Helper to run Celery task or fallback inline for dev."""
    _dispatch_task(
        parse_document_task,
        "documents.parse",
        priority,
        document_id,
        user_id,
        source_url,
        sku,
    )


async def enqueue_generate_analysis(
    document_id: str,
    user_id: str,
    *,
    priority: TaskPriority = TaskPriority.STANDARD,
    sku: str = ANALYSIS_SKU,
) -> Optional[Dict]:
    """Dispatch analysis generation to Celery or run inline."""
    if celery_app and not settings.run_tasks_inline:
        _dispatch_task(
            generate_analysis_task,
            "analysis.generate",
            priority,
            document_id,
            user_id,
            sku,
        )
        return None
    
    # Inline execution
    result = generate_analysis_task(document_id, user_id, sku)
    if asyncio.iscoroutine(result):
        return await result
    return result

