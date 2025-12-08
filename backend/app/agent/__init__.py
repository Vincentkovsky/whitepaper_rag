"""
Agent module for the Generic Agentic RAG System.

This module provides:
- Tool registry and built-in tools
- Hybrid retrieval (vector + BM25)
- Intent routing
- ReAct agent implementation
- Execution tracing
"""

from .types import (
    IntentType,
    IntentClassification,
    ToolSchema,
    Tool,
    AgentResponse,
    AgentStreamEvent,
    ThoughtStep,
)
from .router import IntentRouter
from .react_agent import ReActAgent

__all__ = [
    "IntentType",
    "IntentClassification",
    "ToolSchema",
    "Tool",
    "AgentResponse",
    "AgentStreamEvent",
    "ThoughtStep",
    "IntentRouter",
    "ReActAgent",
]
