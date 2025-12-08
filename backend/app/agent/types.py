"""
Core types and data models for the Agent module.

This module defines all the core types used throughout the agent system,
including intent classification, tool schemas, and agent responses.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentType(Enum):
    """Classification of user intent to determine processing path."""
    DIRECT_ANSWER = "direct_answer"      # Simple greetings, small talk
    DOCUMENT_QA = "document_qa"          # Requires document retrieval
    WEB_SEARCH = "web_search"            # Requires web search
    COMPLEX_REASONING = "complex"        # Requires multi-step reasoning


class IntentClassification(BaseModel):
    """Result of intent classification by the Router."""
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Explanation for the classification")


class ToolSchema(BaseModel):
    """Schema definition for a callable tool."""
    name: str = Field(description="Unique identifier for the tool")
    description: str = Field(description="Human-readable description of what the tool does")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema defining the tool's parameters"
    )
    required: List[str] = Field(
        default_factory=list,
        description="List of required parameter names"
    )


class Tool(BaseModel):
    """A callable tool with its schema and handler function."""
    schema_: ToolSchema = Field(alias="schema", description="The tool's schema definition")
    handler: Callable[..., Any] = Field(description="The function to invoke when the tool is called")

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True

    def __eq__(self, other: object) -> bool:
        """Check equality based on schema (handler comparison is complex)."""
        if not isinstance(other, Tool):
            return False
        return self.schema_ == other.schema_

    def __hash__(self) -> int:
        return hash(self.schema_.name)


class ThoughtStep(BaseModel):
    """A single step in the agent's reasoning process."""
    thought: str = Field(description="The agent's reasoning at this step")
    action: Optional[str] = Field(default=None, description="The tool to invoke, if any")
    action_input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters to pass to the tool"
    )
    observation: Optional[str] = Field(
        default=None,
        description="Result from the tool invocation"
    )


class AgentResponse(BaseModel):
    """Complete response from an agent execution."""
    answer: str = Field(description="The final answer to the user's query")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sources used to generate the answer"
    )
    intermediate_steps: List[ThoughtStep] = Field(
        default_factory=list,
        description="The reasoning steps taken by the agent"
    )
    model_used: str = Field(description="The LLM model used for generation")
    total_latency_ms: float = Field(
        ge=0,
        description="Total execution time in milliseconds"
    )


class AgentStreamEvent(BaseModel):
    """An event emitted during streaming agent execution."""
    event_type: str = Field(
        description="Type of event: 'thinking', 'tool_call', 'tool_result', 'answer'"
    )
    content: str = Field(description="The content of the event")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata for the event"
    )
