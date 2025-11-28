"""
Agent module for the Generic Agentic RAG System.

This module provides:
- Tool registry and built-in tools
- Hybrid retrieval (vector + BM25)
- Intent routing
- ReAct agent implementation
- Execution tracing
"""

from backend.app.agent.types import (
    IntentType,
    IntentClassification,
    ToolSchema,
    Tool,
    AgentResponse,
    AgentStreamEvent,
    ThoughtStep,
)
from backend.app.agent.router import IntentRouter
from backend.app.agent.react_agent import ReActAgent

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
