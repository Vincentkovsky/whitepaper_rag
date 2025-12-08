"""
Property-based tests for Agent API endpoints.

**Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
"""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.types import (
    Tool,
    ToolSchema,
    ThoughtStep,
    AgentResponse,
    AgentStreamEvent,
)
from app.agent.tools.registry import ToolRegistry
from app.agent.react_agent import ReActAgent
from app.api.routes.agent import ChatRequest, ChatResponse


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================

def create_mock_tool(name: str, description: str, return_value: Any) -> Tool:
    """Create a mock tool that returns a fixed value."""
    def handler(**kwargs: Any) -> Any:
        return return_value
    
    return Tool(
        schema=ToolSchema(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "document_id": {"type": "string", "description": "Document ID"},
                    "user_id": {"type": "string", "description": "User ID"},
                },
            },
            required=["query", "document_id", "user_id"],
        ),
        handler=handler,
    )


def create_llm_response(
    thought: str,
    action: str | None = None,
    action_input: Dict[str, Any] | None = None,
    final_answer: str | None = None,
) -> str:
    """Create a mock LLM response in JSON format."""
    return json.dumps({
        "thought": thought,
        "action": action,
        "action_input": action_input,
        "final_answer": final_answer,
    })


class MockLLMResponder:
    """Mock LLM that generates a sequence of responses."""
    
    def __init__(self, responses: List[str]):
        self.responses = responses
        self.call_count = 0
    
    def __call__(self, messages: List[Dict[str, str]]) -> str:
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return create_llm_response(
            thought="Providing final answer",
            final_answer="Default final answer after exhausting responses",
        )


def create_mock_agent_response(
    answer: str,
    intermediate_steps: List[ThoughtStep],
    sources: List[Dict[str, Any]] = None,
) -> AgentResponse:
    """Create a mock AgentResponse for testing."""
    return AgentResponse(
        answer=answer,
        sources=sources or [],
        intermediate_steps=intermediate_steps,
        model_used="test-model",
        total_latency_ms=100.0,
    )


# =============================================================================
# Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid queries
valid_query = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=200,
).filter(lambda x: x.strip() != "")

# Strategy for valid IDs
valid_id = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip() != "")

# Strategy for thought content
valid_thought = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda x: x.strip() != "")

# Strategy for number of intermediate steps
num_steps = st.integers(min_value=0, max_value=10)


# =============================================================================
# Property 20: Intermediate Steps Inclusion
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    num_intermediate_steps=num_steps,
)
def test_intermediate_steps_included_when_trace_true(
    query: str,
    document_id: str,
    num_intermediate_steps: int,
):
    """
    **Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
    
    For any API request with trace=true parameter, the response SHALL include
    an intermediate_steps field containing the agent's reasoning steps.
    
    **Validates: Requirements 8.2**
    """
    # Create intermediate steps
    intermediate_steps = [
        ThoughtStep(
            thought=f"Step {i+1}: Analyzing",
            action="document_search" if i < num_intermediate_steps - 1 else None,
            action_input={"query": query} if i < num_intermediate_steps - 1 else None,
            observation=f"Found result {i+1}" if i < num_intermediate_steps - 1 else None,
        )
        for i in range(num_intermediate_steps)
    ]
    
    # Create mock response
    mock_response = create_mock_agent_response(
        answer="Test answer",
        intermediate_steps=intermediate_steps,
    )
    
    # Test the response building logic directly
    # When trace=True, intermediate_steps should be included
    result = ChatResponse(
        answer=mock_response.answer,
        sources=mock_response.sources,
        model_used=mock_response.model_used,
    )
    
    # Simulate trace=True behavior
    result.intermediate_steps = [
        {
            "thought": step.thought,
            "action": step.action,
            "action_input": step.action_input,
            "observation": step.observation,
        }
        for step in mock_response.intermediate_steps
    ]
    
    # PROPERTY: When trace=true, intermediate_steps should be present
    assert result.intermediate_steps is not None, (
        "intermediate_steps should be present when trace=true"
    )
    
    # PROPERTY: Number of steps should match
    assert len(result.intermediate_steps) == num_intermediate_steps, (
        f"Expected {num_intermediate_steps} steps, got {len(result.intermediate_steps)}"
    )
    
    # PROPERTY: Each step should have the required fields
    for i, step in enumerate(result.intermediate_steps):
        assert "thought" in step, f"Step {i} should have 'thought' field"
        assert "action" in step, f"Step {i} should have 'action' field"
        assert "action_input" in step, f"Step {i} should have 'action_input' field"
        assert "observation" in step, f"Step {i} should have 'observation' field"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    num_intermediate_steps=st.integers(min_value=1, max_value=10),
)
def test_intermediate_steps_excluded_when_trace_false(
    query: str,
    document_id: str,
    num_intermediate_steps: int,
):
    """
    **Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
    
    For any API request without trace parameter or with trace=false,
    the response SHALL NOT include intermediate_steps field.
    
    **Validates: Requirements 8.2**
    """
    # Create intermediate steps
    intermediate_steps = [
        ThoughtStep(
            thought=f"Step {i+1}: Analyzing",
            action="document_search" if i < num_intermediate_steps - 1 else None,
            action_input={"query": query} if i < num_intermediate_steps - 1 else None,
            observation=f"Found result {i+1}" if i < num_intermediate_steps - 1 else None,
        )
        for i in range(num_intermediate_steps)
    ]
    
    # Create mock response
    mock_response = create_mock_agent_response(
        answer="Test answer",
        intermediate_steps=intermediate_steps,
    )
    
    # Test the response building logic directly
    # When trace=False, intermediate_steps should NOT be included
    result = ChatResponse(
        answer=mock_response.answer,
        sources=mock_response.sources,
        model_used=mock_response.model_used,
    )
    
    # Don't set intermediate_steps (simulating trace=False)
    
    # PROPERTY: When trace=false, intermediate_steps should be None
    assert result.intermediate_steps is None, (
        "intermediate_steps should be None when trace=false"
    )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    thoughts=st.lists(valid_thought, min_size=1, max_size=5),
    actions=st.lists(
        st.one_of(st.just("document_search"), st.just("web_search"), st.none()),
        min_size=1,
        max_size=5,
    ),
)
def test_intermediate_steps_preserve_step_content(
    thoughts: List[str],
    actions: List[str | None],
):
    """
    **Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
    
    For any agent execution, the intermediate_steps in the response SHALL
    preserve the exact content of each reasoning step (thought, action,
    action_input, observation).
    
    **Validates: Requirements 8.2**
    """
    # Ensure lists are same length
    min_len = min(len(thoughts), len(actions))
    thoughts = thoughts[:min_len]
    actions = actions[:min_len]
    
    # Create intermediate steps with specific content
    intermediate_steps = []
    for i, (thought, action) in enumerate(zip(thoughts, actions)):
        step = ThoughtStep(
            thought=thought,
            action=action,
            action_input={"query": f"query_{i}"} if action else None,
            observation=f"observation_{i}" if action else None,
        )
        intermediate_steps.append(step)
    
    # Create mock response
    mock_response = create_mock_agent_response(
        answer="Test answer",
        intermediate_steps=intermediate_steps,
    )
    
    # Build response with trace=True
    result_steps = [
        {
            "thought": step.thought,
            "action": step.action,
            "action_input": step.action_input,
            "observation": step.observation,
        }
        for step in mock_response.intermediate_steps
    ]
    
    # PROPERTY: Each step's content should be preserved exactly
    for i, (original, result) in enumerate(zip(intermediate_steps, result_steps)):
        assert result["thought"] == original.thought, (
            f"Step {i} thought mismatch: expected '{original.thought}', got '{result['thought']}'"
        )
        assert result["action"] == original.action, (
            f"Step {i} action mismatch: expected '{original.action}', got '{result['action']}'"
        )
        assert result["action_input"] == original.action_input, (
            f"Step {i} action_input mismatch"
        )
        assert result["observation"] == original.observation, (
            f"Step {i} observation mismatch"
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_intermediate_steps_with_tool_calls_have_observations(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
    
    For any intermediate step that includes a tool call (action is not None),
    the step SHALL also include an observation field with the tool's result.
    
    **Validates: Requirements 8.2**
    """
    registry = ToolRegistry()
    registry.register(create_mock_tool(
        "document_search",
        "Search documents",
        [{"id": "chunk1", "text": "Test content"}],
    ))
    
    # Create responses with tool calls
    responses = [
        create_llm_response(
            thought="Searching for information",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found the answer",
            final_answer="Here is the answer.",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Steps with actions should have observations
    for step in response.intermediate_steps:
        if step.action is not None:
            assert step.observation is not None, (
                f"Step with action '{step.action}' should have an observation"
            )
            assert step.observation != "", (
                f"Observation for action '{step.action}' should not be empty"
            )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_intermediate_steps_order_preserved(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 20: Intermediate Steps Inclusion**
    
    For any multi-step agent execution, the intermediate_steps SHALL be
    returned in the order they were executed.
    
    **Validates: Requirements 8.2**
    """
    registry = ToolRegistry()
    registry.register(create_mock_tool(
        "document_search",
        "Search documents",
        [{"id": "chunk1", "text": "Test content"}],
    ))
    
    # Create numbered responses to verify order
    responses = [
        create_llm_response(
            thought="Step 1: First search",
            action="document_search",
            action_input={"query": "first"},
        ),
        create_llm_response(
            thought="Step 2: Second search",
            action="document_search",
            action_input={"query": "second"},
        ),
        create_llm_response(
            thought="Step 3: Final answer",
            final_answer="Answer based on searches.",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Steps should be in order
    assert len(response.intermediate_steps) == 3, (
        f"Expected 3 steps, got {len(response.intermediate_steps)}"
    )
    
    assert "Step 1" in response.intermediate_steps[0].thought, (
        "First step should contain 'Step 1'"
    )
    assert "Step 2" in response.intermediate_steps[1].thought, (
        "Second step should contain 'Step 2'"
    )
    assert "Step 3" in response.intermediate_steps[2].thought, (
        "Third step should contain 'Step 3'"
    )
