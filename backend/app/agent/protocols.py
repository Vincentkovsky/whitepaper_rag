"""
Protocol definitions for the Agent module.

This module defines the interfaces (Protocols) that components must implement,
enabling loose coupling and easier testing.
"""

from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

from .types import (
    AgentResponse,
    AgentStreamEvent,
    IntentClassification,
    Tool,
    ToolSchema,
)


@runtime_checkable
class IntentRouter(Protocol):
    """Protocol for intent classification components."""

    def classify(self, query: str, context: Optional[Dict[str, Any]] = None) -> IntentClassification:
        """Classify user intent to determine processing path.

        Args:
            query: The user's input query
            context: Optional context information (e.g., conversation history)

        Returns:
            IntentClassification with intent type, confidence, and reasoning

        Note:
            Fallback mechanism: If DIRECT_ANSWER confidence < 0.8,
            automatically escalate to DOCUMENT_QA to avoid false negatives.
        """
        ...


@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Protocol for tool registry implementations."""

    def register(self, tool: Tool) -> None:
        """Register a tool with the registry.

        Args:
            tool: The tool to register
        """
        ...

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: The unique name of the tool

        Returns:
            The tool if found, None otherwise
        """
        ...


    def list_tools(self) -> List[ToolSchema]:
        """List all registered tool schemas.

        Returns:
            List of all registered tool schemas
        """
        ...

    def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke a tool by name with given parameters.

        Args:
            name: The name of the tool to invoke
            **kwargs: Parameters to pass to the tool

        Returns:
            The result of the tool invocation

        Raises:
            ValueError: If the tool is not found
        """
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for agent implementations."""

    async def run(
        self,
        query: str,
        document_id: str,
        user_id: str,
        stream: bool = False,
    ) -> AgentResponse:
        """Execute agent reasoning loop.

        Args:
            query: The user's question
            document_id: ID of the document to query
            user_id: ID of the user making the request
            stream: Whether to enable streaming (affects internal behavior)

        Returns:
            AgentResponse with answer, sources, and intermediate steps
        """
        ...

    async def stream(
        self,
        query: str,
        document_id: str,
        user_id: str,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Stream agent execution events.

        Args:
            query: The user's question
            document_id: ID of the document to query
            user_id: ID of the user making the request

        Yields:
            AgentStreamEvent for each step of execution
        """
        ...


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for retrieval implementations."""

    def search(
        self,
        query: str,
        document_id: str,
        user_id: str,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Perform search to retrieve relevant chunks.

        Args:
            query: The search query
            document_id: ID of the document to search
            user_id: ID of the user making the request
            k: Number of results to return

        Returns:
            List of retrieval results with chunk text and metadata
        """
        ...


@runtime_checkable
class TracerProtocol(Protocol):
    """Protocol for execution tracing implementations."""

    def start_span(self, name: str, inputs: Dict[str, Any]) -> str:
        """Start a new trace span.

        Args:
            name: Name of the span (e.g., "tool_call", "llm_call")
            inputs: Input data for this span

        Returns:
            Unique span_id for this span
        """
        ...

    def end_span(self, span_id: str, outputs: Dict[str, Any]) -> None:
        """End a trace span with outputs.

        Args:
            span_id: The ID of the span to end
            outputs: Output data from this span
        """
        ...

    def get_trace(self) -> Dict[str, Any]:
        """Get the complete execution trace.

        Returns:
            ExecutionTrace with all spans and total latency
        """
        ...

    def export_langsmith(self) -> Dict[str, Any]:
        """Export trace in LangSmith compatible format.

        Returns:
            Dictionary conforming to LangSmith trace schema
        """
        ...
