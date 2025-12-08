"""
Agent Service - Orchestrates all agent components.

This service provides a unified interface for the Agentic RAG system,
coordinating the Router, ReAct Agent, Hybrid Retriever, and Execution Tracer.

Requirements:
- 1.1: WHEN a user submits a question, THE Agentic_RAG_System SHALL initiate
       the response stream within 3 seconds.
- 2.2: WHEN the Agent determines a tool is needed, THE Agentic_RAG_System SHALL
       invoke the tool with appropriate parameters and incorporate the result.
- 3.1: WHEN a user submits a complex question, THE Agentic_RAG_System SHALL
       decompose it into sub-questions and process them sequentially.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import chromadb

from ..core.config import get_settings, Settings
from ..agent.react_agent import ReActAgent
from ..agent.router import IntentRouter
from ..agent.tools.registry import ToolRegistry
from ..agent.tools.document_search import create_document_search_tool
from ..agent.tracing.tracer import ExecutionTracer, ExecutionTrace
from ..agent.retrieval.hybrid_retriever import HybridRetriever
from ..agent.retrieval.bm25_store import BM25IndexStore
from ..agent.types import AgentResponse, AgentStreamEvent
from .rag_service import RAGService


logger = logging.getLogger(__name__)


class AgentService:
    """
    Orchestrates all agent components for the Agentic RAG system.
    
    This service provides:
    - Intent routing for query classification
    - ReAct agent for multi-step reasoning
    - Hybrid retrieval (vector + BM25)
    - Execution tracing for observability
    
    Example:
        >>> service = AgentService()
        >>> response = await service.chat(
        ...     query="What is the main topic?",
        ...     document_id="doc123",
        ...     user_id="user456",
        ... )
        >>> print(response.answer)
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        rag_service: Optional[RAGService] = None,
        chroma_client: Optional[chromadb.Client] = None,
        router: Optional[IntentRouter] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        """
        Initialize the AgentService with all components.
        
        Args:
            settings: Application settings (uses defaults if not provided)
            rag_service: RAG service for document retrieval
            chroma_client: ChromaDB client for vector search
            router: Intent router (creates default if not provided)
            tool_registry: Tool registry (creates default with built-in tools if not provided)
        """
        self._settings = settings or get_settings()
        
        # Initialize RAG service
        self._rag_service = rag_service or RAGService()
        
        # Initialize ChromaDB client
        if chroma_client:
            self._chroma = chroma_client
        else:
            self._chroma = self._create_chroma_client()
        
        # Initialize BM25 store
        self._bm25_store = BM25IndexStore()
        
        # Initialize hybrid retriever
        self._hybrid_retriever = HybridRetriever(
            chroma_client=self._chroma,
            bm25_store=self._bm25_store,
            vector_weight=self._settings.vector_weight,
            bm25_weight=self._settings.bm25_weight,
        )
        
        # Initialize intent router
        self._router = router or IntentRouter(
            confidence_threshold=self._settings.router_confidence_threshold,
        )
        
        # Initialize tool registry with built-in tools
        self._tool_registry = tool_registry or self._create_default_tool_registry()
        
        # Initialize the ReAct agent
        self._agent = ReActAgent(
            tool_registry=self._tool_registry,
            router=self._router,
            max_steps=self._settings.agent_max_steps,
        )
        
        logger.info(
            "AgentService initialized",
            extra={
                "max_steps": self._settings.agent_max_steps,
                "vector_weight": self._settings.vector_weight,
                "bm25_weight": self._settings.bm25_weight,
                "router_threshold": self._settings.router_confidence_threshold,
            },
        )
    
    @property
    def router(self) -> IntentRouter:
        """Get the intent router."""
        return self._router
    
    @property
    def agent(self) -> ReActAgent:
        """Get the ReAct agent."""
        return self._agent
    
    @property
    def hybrid_retriever(self) -> HybridRetriever:
        """Get the hybrid retriever."""
        return self._hybrid_retriever
    
    @property
    def tool_registry(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._tool_registry
    
    async def chat(
        self,
        query: str,
        user_id: str,
        trace_enabled: bool = False,
    ) -> AgentResponse:
        """
        Process a chat query using the agent.
        
        The agent will search across all documents belonging to the user.
        
        Args:
            query: The user's question
            user_id: ID of the user making the request
            trace_enabled: Whether to enable execution tracing
            
        Returns:
            AgentResponse with answer, sources, and optionally intermediate steps
        """
        start_time = time.perf_counter()
        tracer: Optional[ExecutionTracer] = None
        
        if trace_enabled:
            tracer = ExecutionTracer()
            span_id = tracer.start_span(
                name="agent_chat",
                inputs={"query": query, "user_id": user_id},
            )
        
        try:
            response = await self._agent.run(
                query=query,
                user_id=user_id,
                stream=False,
            )
            
            if tracer:
                tracer.end_span(span_id, {
                    "answer": response.answer,
                    "steps": len(response.intermediate_steps),
                })
            
            return response
            
        except Exception as e:
            logger.error(f"Agent chat failed: {e}", exc_info=True)
            if tracer:
                tracer.end_span(span_id, {"error": str(e)})
            raise
    
    async def chat_stream(
        self,
        query: str,
        user_id: str,
        trace_enabled: bool = False,
    ) -> AsyncIterator[AgentStreamEvent]:
        """
        Stream chat responses from the agent.
        
        The agent will search across all documents belonging to the user.
        
        Args:
            query: The user's question
            user_id: ID of the user making the request
            trace_enabled: Whether to enable execution tracing
            
        Yields:
            AgentStreamEvent for each step of execution
        """
        tracer: Optional[ExecutionTracer] = None
        
        if trace_enabled:
            tracer = ExecutionTracer()
            tracer.start_span(
                name="agent_stream",
                inputs={"query": query, "user_id": user_id},
            )
        
        try:
            async for event in self._agent.stream(
                query=query,
                user_id=user_id,
            ):
                yield event
                
        except Exception as e:
            logger.error(f"Agent stream failed: {e}", exc_info=True)
            yield AgentStreamEvent(
                event_type="error",
                content=str(e),
            )
    
    def get_trace(self, tracer: ExecutionTracer) -> ExecutionTrace:
        """
        Get the execution trace from a tracer.
        
        Args:
            tracer: The execution tracer
            
        Returns:
            ExecutionTrace with all spans
        """
        return tracer.get_trace()
    
    def _create_chroma_client(self) -> chromadb.Client:
        """Create a ChromaDB client based on settings."""
        if self._settings.chroma_server_host:
            return chromadb.HttpClient(
                host=self._settings.chroma_server_host,
                port=self._settings.chroma_server_port,
                ssl=self._settings.chroma_server_ssl,
                headers=(
                    {"Authorization": f"Bearer {self._settings.chroma_server_api_key}"}
                    if self._settings.chroma_server_api_key
                    else None
                ),
            )
        elif self._settings.chroma_persist_directory:
            from pathlib import Path
            from chromadb.config import Settings as ChromaSettings
            
            persist_dir = Path(self._settings.chroma_persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)
            
            chroma_settings = ChromaSettings(
                persist_directory=str(persist_dir),
                anonymized_telemetry=False,
            )
            return chromadb.PersistentClient(
                path=str(persist_dir),
                settings=chroma_settings,
            )
        else:
            from chromadb.config import Settings as ChromaSettings
            return chromadb.Client(settings=ChromaSettings(anonymized_telemetry=False))
    
    def _create_default_tool_registry(self) -> ToolRegistry:
        """Create a tool registry with default built-in tools."""
        registry = ToolRegistry()
        
        # Register document search tool
        doc_search_tool = create_document_search_tool(self._rag_service)
        registry.register(doc_search_tool)
        
        # Try to register web search tool if API key is available
        if self._settings.tavily_api_key:
            try:
                from ..agent.tools.web_search import create_web_search_tool
                web_search_tool = create_web_search_tool(self._settings.tavily_api_key)
                registry.register(web_search_tool)
                logger.info("Web search tool registered")
            except Exception as e:
                logger.warning(f"Failed to register web search tool: {e}")
        
        return registry


# Dependency injection helper
_agent_service_instance: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """
    Get or create the singleton AgentService instance.
    
    Returns:
        The AgentService instance
    """
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = AgentService()
    return _agent_service_instance


def reset_agent_service() -> None:
    """Reset the singleton AgentService instance (useful for testing)."""
    global _agent_service_instance
    _agent_service_instance = None
