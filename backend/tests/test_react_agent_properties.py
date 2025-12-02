import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for ReAct Agent.

**Feature: generic-agentic-rag, Property 8: State Preservation Across Steps**
**Feature: generic-agentic-rag, Property 9: Step Limit Invariant**
**Feature: generic-agentic-rag, Property 10: Final Answer Synthesis**
"""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from app.agent.types import Tool, ToolSchema, ThoughtStep
from app.agent.tools.registry import ToolRegistry
from app.agent.react_agent import ReActAgent, DEFAULT_MAX_STEPS


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


def create_registry_with_tools() -> ToolRegistry:
    """Create a registry with standard test tools."""
    registry = ToolRegistry()
    registry.register(create_mock_tool(
        "document_search",
        "Search for relevant information in documents",
        [{"id": "chunk1", "text": "Test content", "section": "intro"}],
    ))
    return registry


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
    """
    Mock LLM that generates a sequence of responses.
    
    Used to control the agent's behavior in tests by providing
    predetermined responses that simulate multi-step reasoning.
    """
    
    def __init__(self, responses: List[str]):
        """
        Initialize with a list of responses to return in sequence.
        
        Args:
            responses: List of JSON-formatted response strings
        """
        self.responses = responses
        self.call_count = 0
    
    def __call__(self, messages: List[Dict[str, str]]) -> str:
        """Return the next response in sequence."""
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        # If we run out of responses, return a final answer
        return create_llm_response(
            thought="Providing final answer",
            final_answer="Default final answer after exhausting responses",
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

# Strategy for max_steps values
valid_max_steps = st.integers(min_value=1, max_value=20)

# Strategy for number of tool calls (for multi-step tests)
num_tool_calls = st.integers(min_value=1, max_value=15)


# =============================================================================
# Property 9: Step Limit Invariant
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
    max_steps=valid_max_steps,
    num_responses=st.integers(min_value=1, max_value=25),
)
def test_step_limit_invariant(
    query: str,
    document_id: str,
    user_id: str,
    max_steps: int,
    num_responses: int,
):
    """
    **Feature: generic-agentic-rag, Property 9: Step Limit Invariant**
    
    For any agent execution, the number of reasoning steps SHALL NOT exceed
    the configured max_steps limit.
    
    **Validates: Requirements 3.3**
    """
    registry = create_registry_with_tools()
    
    # Create responses that keep calling tools (never provide final answer)
    # This tests that the agent respects the step limit
    responses = [
        create_llm_response(
            thought=f"Step {i+1}: Need more information",
            action="document_search",
            action_input={"query": query},
        )
        for i in range(num_responses)
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    # Create agent with specified max_steps
    agent = ReActAgent(
        tool_registry=registry,
        router=None,  # No router to ensure we go through the reasoning loop
        max_steps=max_steps,
    )
    
    # Mock the LLM call
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        # Run the agent
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Number of intermediate steps SHALL NOT exceed max_steps
    assert len(response.intermediate_steps) <= max_steps, (
        f"Agent took {len(response.intermediate_steps)} steps, "
        f"but max_steps is {max_steps}"
    )
    
    # PROPERTY: Agent should always produce a response (even if step limit reached)
    assert response.answer is not None, "Agent should always produce an answer"
    assert response.answer != "", "Agent answer should not be empty"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_step_limit_default_value(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 9: Step Limit Invariant**
    
    The default max_steps value SHALL be 10, and the agent SHALL respect
    this default when no explicit value is provided.
    
    **Validates: Requirements 3.3**
    """
    registry = create_registry_with_tools()
    
    # Create more responses than the default limit
    responses = [
        create_llm_response(
            thought=f"Step {i+1}: Searching",
            action="document_search",
            action_input={"query": query},
        )
        for i in range(20)  # More than default 10
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    # Create agent with default max_steps
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
    )
    
    # Verify default value
    assert agent.max_steps == DEFAULT_MAX_STEPS == 10, (
        f"Default max_steps should be 10, got {agent.max_steps}"
    )
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Steps should not exceed default limit
    assert len(response.intermediate_steps) <= DEFAULT_MAX_STEPS



# =============================================================================
# Property 8: State Preservation Across Steps
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
    num_steps=st.integers(min_value=2, max_value=5),
)
def test_state_preservation_across_steps(
    query: str,
    document_id: str,
    user_id: str,
    num_steps: int,
):
    """
    **Feature: generic-agentic-rag, Property 8: State Preservation Across Steps**
    
    For any multi-step agent execution, information gathered in earlier steps
    SHALL be accessible in later steps (verified by checking that later steps
    can reference earlier observations).
    
    **Validates: Requirements 3.2**
    """
    registry = create_registry_with_tools()
    
    # Create a sequence of responses that build on each other
    # Each step references information from previous steps
    observations = [f"Observation_{i}_data" for i in range(num_steps)]
    
    responses = []
    for i in range(num_steps - 1):
        responses.append(create_llm_response(
            thought=f"Step {i+1}: Found {observations[i]}, need more info",
            action="document_search",
            action_input={"query": f"follow up on {observations[i]}"},
        ))
    
    # Final response synthesizes all observations
    responses.append(create_llm_response(
        thought=f"Have gathered all information from steps 1-{num_steps}",
        final_answer=f"Based on observations: {', '.join(observations[:num_steps-1])}",
    ))
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=num_steps + 5,  # Allow enough steps
    )
    
    # Track conversation history to verify state preservation
    conversation_histories = []
    original_call_llm = agent._call_llm
    
    def tracking_call_llm(messages):
        conversation_histories.append(messages.copy())
        return mock_responder(messages)
    
    with patch.object(agent, '_call_llm', side_effect=tracking_call_llm):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Each subsequent LLM call should include previous observations
    # The conversation history should grow with each step
    for i in range(1, len(conversation_histories)):
        current_history = conversation_histories[i]
        previous_history = conversation_histories[i - 1]
        
        # Current history should be longer (includes previous response + observation)
        assert len(current_history) >= len(previous_history), (
            f"Conversation history should grow: step {i} has {len(current_history)} messages, "
            f"step {i-1} had {len(previous_history)} messages"
        )
    
    # PROPERTY: Intermediate steps should be recorded
    assert len(response.intermediate_steps) >= 1, (
        "Multi-step execution should record intermediate steps"
    )
    
    # PROPERTY: Each step should have a thought
    for step in response.intermediate_steps:
        assert step.thought is not None, "Each step should have a thought"
        assert step.thought != "", "Thought should not be empty"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_observations_accumulated_in_steps(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 8: State Preservation Across Steps**
    
    For any agent execution with tool calls, observations from tool invocations
    SHALL be recorded in the intermediate steps.
    
    **Validates: Requirements 3.2**
    """
    registry = create_registry_with_tools()
    
    # Two tool calls followed by final answer
    responses = [
        create_llm_response(
            thought="First search",
            action="document_search",
            action_input={"query": "first query"},
        ),
        create_llm_response(
            thought="Second search based on first results",
            action="document_search",
            action_input={"query": "second query"},
        ),
        create_llm_response(
            thought="Have enough information",
            final_answer="Final answer based on both searches",
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
    
    # PROPERTY: Steps with tool calls should have observations
    steps_with_actions = [s for s in response.intermediate_steps if s.action is not None]
    
    for step in steps_with_actions:
        assert step.observation is not None, (
            f"Step with action '{step.action}' should have an observation"
        )


# =============================================================================
# Property 10: Final Answer Synthesis
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_final_answer_synthesis_on_completion(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 10: Final Answer Synthesis**
    
    For any multi-step agent execution that completes successfully,
    the response SHALL contain a non-empty final answer.
    
    **Validates: Requirements 3.4**
    """
    registry = create_registry_with_tools()
    
    # Normal execution with tool call and final answer
    responses = [
        create_llm_response(
            thought="Searching for information",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found relevant information",
            final_answer="Here is the synthesized answer based on the search results.",
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
    
    # PROPERTY: Response should have a non-empty answer
    assert response.answer is not None, "Response should have an answer"
    assert response.answer != "", "Answer should not be empty"
    assert len(response.answer) > 0, "Answer should have content"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
    max_steps=st.integers(min_value=1, max_value=5),
)
def test_final_answer_synthesis_on_step_limit(
    query: str,
    document_id: str,
    user_id: str,
    max_steps: int,
):
    """
    **Feature: generic-agentic-rag, Property 10: Final Answer Synthesis**
    
    For any agent execution that reaches the step limit without a final answer,
    the agent SHALL synthesize a final answer from available observations.
    
    **Validates: Requirements 3.4**
    """
    registry = create_registry_with_tools()
    
    # Create responses that never provide a final answer
    # This forces the agent to synthesize one when step limit is reached
    responses = [
        create_llm_response(
            thought=f"Step {i+1}: Still searching",
            action="document_search",
            action_input={"query": f"search {i+1}"},
        )
        for i in range(max_steps + 5)  # More responses than steps allowed
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=max_steps,
    )
    
    # Mock the synthesis method to track if it's called
    synthesis_called = False
    original_synthesize = agent._synthesize_final_answer
    
    def tracking_synthesize(*args, **kwargs):
        nonlocal synthesis_called
        synthesis_called = True
        return original_synthesize(*args, **kwargs)
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        with patch.object(agent, '_synthesize_final_answer', side_effect=tracking_synthesize):
            response = asyncio.get_event_loop().run_until_complete(
                agent.run(query=query, document_id=document_id, user_id=user_id)
            )
    
    # PROPERTY: Synthesis should be called when step limit reached without final answer
    assert synthesis_called, (
        "Agent should synthesize final answer when step limit is reached"
    )
    
    # PROPERTY: Response should still have a non-empty answer
    assert response.answer is not None, "Response should have an answer even after step limit"
    assert response.answer != "", "Synthesized answer should not be empty"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_final_answer_includes_model_info(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 10: Final Answer Synthesis**
    
    For any agent execution, the response SHALL include metadata about
    the model used and execution latency.
    
    **Validates: Requirements 3.4**
    """
    registry = create_registry_with_tools()
    
    responses = [
        create_llm_response(
            thought="Direct answer",
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
    
    # PROPERTY: Response should include model information
    assert response.model_used is not None, "Response should include model_used"
    assert response.model_used != "", "model_used should not be empty"
    
    # PROPERTY: Response should include latency
    assert response.total_latency_ms is not None, "Response should include latency"
    assert response.total_latency_ms >= 0, "Latency should be non-negative"


# =============================================================================
# Property 1: Stream Initiation Latency
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_stream_initiation_latency(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 1: Stream Initiation Latency**
    
    For any valid user query, the system SHALL emit the first stream event
    within 3 seconds of receiving the request.
    
    **Validates: Requirements 1.1**
    """
    import time
    
    registry = create_registry_with_tools()
    
    # Create a response that will be returned by the mock LLM
    responses = [
        create_llm_response(
            thought="Analyzing the query",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found information",
            final_answer="Here is the answer based on the search.",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    async def measure_first_event_latency():
        start_time = time.perf_counter()
        first_event_time = None
        first_event = None
        
        with patch.object(agent, '_call_llm', side_effect=mock_responder):
            async for event in agent.stream(
                query=query,
                document_id=document_id,
                user_id=user_id,
            ):
                if first_event_time is None:
                    first_event_time = time.perf_counter()
                    first_event = event
                # Continue consuming events to complete the stream
        
        latency_seconds = first_event_time - start_time if first_event_time else float('inf')
        return latency_seconds, first_event
    
    latency, first_event = asyncio.get_event_loop().run_until_complete(
        measure_first_event_latency()
    )
    
    # PROPERTY: First event should be emitted within 3 seconds
    assert latency < 3.0, (
        f"First stream event took {latency:.3f} seconds, "
        f"but should be within 3 seconds"
    )
    
    # PROPERTY: First event should be a valid event type
    assert first_event is not None, "Stream should emit at least one event"
    assert first_event.event_type in ("thinking", "tool_call", "tool_result", "answer"), (
        f"First event type '{first_event.event_type}' is not a valid event type"
    )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_stream_emits_all_event_types(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 1: Stream Initiation Latency**
    
    For any agent execution with tool calls, the stream SHALL emit events
    for: thinking, tool_call, tool_result, and answer.
    
    **Validates: Requirements 1.1**
    """
    registry = create_registry_with_tools()
    
    # Create responses that include a tool call
    responses = [
        create_llm_response(
            thought="I need to search the document",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found the information",
            final_answer="Here is the answer.",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    async def collect_events():
        events = []
        with patch.object(agent, '_call_llm', side_effect=mock_responder):
            async for event in agent.stream(
                query=query,
                document_id=document_id,
                user_id=user_id,
            ):
                events.append(event)
        return events
    
    events = asyncio.get_event_loop().run_until_complete(collect_events())
    
    # Collect event types
    event_types = {e.event_type for e in events}
    
    # PROPERTY: Stream should emit thinking events
    assert "thinking" in event_types, "Stream should emit 'thinking' events"
    
    # PROPERTY: Stream should emit tool_call events (since we have a tool call)
    assert "tool_call" in event_types, "Stream should emit 'tool_call' events"
    
    # PROPERTY: Stream should emit tool_result events
    assert "tool_result" in event_types, "Stream should emit 'tool_result' events"
    
    # PROPERTY: Stream should emit answer event
    assert "answer" in event_types, "Stream should emit 'answer' event"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_stream_ends_with_answer_event(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 1: Stream Initiation Latency**
    
    For any agent execution, the stream SHALL end with an 'answer' event
    containing the final response.
    
    **Validates: Requirements 1.1**
    """
    registry = create_registry_with_tools()
    
    responses = [
        create_llm_response(
            thought="Processing query",
            final_answer="Final answer to the query.",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    async def collect_events():
        events = []
        with patch.object(agent, '_call_llm', side_effect=mock_responder):
            async for event in agent.stream(
                query=query,
                document_id=document_id,
                user_id=user_id,
            ):
                events.append(event)
        return events
    
    events = asyncio.get_event_loop().run_until_complete(collect_events())
    
    # PROPERTY: Stream should have at least one event
    assert len(events) > 0, "Stream should emit at least one event"
    
    # PROPERTY: Last event should be an answer
    last_event = events[-1]
    assert last_event.event_type == "answer", (
        f"Last event should be 'answer', got '{last_event.event_type}'"
    )
    
    # PROPERTY: Answer event should have non-empty content
    assert last_event.content is not None, "Answer event should have content"
    assert last_event.content != "", "Answer content should not be empty"


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=valid_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_agent_handles_immediate_final_answer(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    Test that agent correctly handles LLM providing immediate final answer
    without any tool calls.
    """
    registry = create_registry_with_tools()
    
    # LLM immediately provides final answer
    responses = [
        create_llm_response(
            thought="I can answer this directly",
            final_answer="Direct answer without tool use.",
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
    
    # Should have exactly one step (the final answer step)
    assert len(response.intermediate_steps) == 1
    assert response.intermediate_steps[0].action is None
    assert response.answer == "Direct answer without tool use."
