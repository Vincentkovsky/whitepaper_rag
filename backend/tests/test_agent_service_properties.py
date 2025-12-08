"""
Property-based tests for AgentService integration.

**Feature: generic-agentic-rag, Property 2: Bilingual Query Support**
**Feature: generic-agentic-rag, Property 4: Tool Result Incorporation**
**Feature: generic-agentic-rag, Property 7: Complex Query Decomposition**
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from app.agent.types import Tool, ToolSchema, ThoughtStep, AgentResponse
from app.agent.tools.registry import ToolRegistry
from app.agent.react_agent import ReActAgent
from app.agent.router import IntentRouter


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
        [{"id": "chunk1", "text": "Test content about the topic", "section": "intro"}],
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
            final_answer="Default final answer",
        )


# =============================================================================
# Strategies for Property-Based Testing
# =============================================================================

# Strategy for Chinese text queries
chinese_query = st.text(
    alphabet="你好吗这是一个测试问题关于文档内容请帮我查找信息什么怎么为何如何",
    min_size=2,
    max_size=50,
).filter(lambda x: x.strip() != "")

# Strategy for English text queries
english_query = st.text(
    alphabet=st.characters(
        whitelist_categories=("L",),
        whitelist_characters=" ?!.,",
    ),
    min_size=2,
    max_size=100,
).filter(lambda x: x.strip() != "" and any(c.isalpha() for c in x))

# Strategy for mixed bilingual queries
bilingual_query = st.one_of(
    chinese_query,
    english_query,
    # Mixed Chinese and English
    st.tuples(chinese_query, english_query).map(lambda t: f"{t[0]} {t[1]}"),
)

# Strategy for valid IDs
valid_id = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip() != "")

# Strategy for complex multi-part questions
complex_question_parts = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
        min_size=5,
        max_size=50,
    ).filter(lambda x: x.strip() != ""),
    min_size=2,
    max_size=4,
)


# =============================================================================
# Property 2: Bilingual Query Support
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=bilingual_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_bilingual_query_support_produces_valid_response(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 2: Bilingual Query Support**
    
    For any question in Chinese or English, the system SHALL produce a valid
    response without language-specific errors.
    
    **Validates: Requirements 1.4**
    """
    registry = create_registry_with_tools()
    
    # Create responses that handle the query
    responses = [
        create_llm_response(
            thought=f"Processing query: {query[:30]}...",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found relevant information",
            final_answer=f"Answer for: {query[:20]}...",
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
    
    # PROPERTY: Response should be valid regardless of language
    assert response is not None, "Response should not be None"
    assert isinstance(response, AgentResponse), "Response should be AgentResponse"
    
    # PROPERTY: Answer should be non-empty
    assert response.answer is not None, "Answer should not be None"
    assert response.answer != "", "Answer should not be empty"
    
    # PROPERTY: Response should have valid metadata
    assert response.model_used is not None, "model_used should be set"
    assert response.total_latency_ms >= 0, "Latency should be non-negative"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=chinese_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_chinese_query_no_encoding_errors(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 2: Bilingual Query Support**
    
    For any Chinese query, the system SHALL process it without encoding errors
    and produce a valid response.
    
    **Validates: Requirements 1.4**
    """
    registry = create_registry_with_tools()
    
    responses = [
        create_llm_response(
            thought=f"处理中文查询: {query}",
            final_answer=f"回答: {query}",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    # This should not raise any encoding errors
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        try:
            response = asyncio.get_event_loop().run_until_complete(
                agent.run(query=query, document_id=document_id, user_id=user_id)
            )
            # PROPERTY: No exception should be raised for Chinese text
            assert response.answer is not None
        except UnicodeError as e:
            pytest.fail(f"Chinese query caused encoding error: {e}")


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=english_query,
    document_id=valid_id,
    user_id=valid_id,
)
def test_english_query_produces_valid_response(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 2: Bilingual Query Support**
    
    For any English query, the system SHALL produce a valid response.
    
    **Validates: Requirements 1.4**
    """
    registry = create_registry_with_tools()
    
    responses = [
        create_llm_response(
            thought=f"Processing English query: {query[:30]}",
            final_answer=f"Answer for: {query[:20]}",
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
    
    # PROPERTY: English queries should produce valid responses
    assert response is not None
    assert response.answer is not None
    assert response.answer != ""


# =============================================================================
# Property 4: Tool Result Incorporation
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=st.text(min_size=1, max_size=100).filter(lambda x: x.strip() != ""),
    document_id=valid_id,
    user_id=valid_id,
)
def test_tool_result_appears_in_intermediate_steps(
    query: str,
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 4: Tool Result Incorporation**
    
    For any agent execution that invokes a tool, the tool's result SHALL appear
    in the agent's intermediate_steps.
    
    **Validates: Requirements 2.2**
    """
    # Create a tool with a distinctive return value
    tool_result = [{"id": "test_chunk", "text": "DISTINCTIVE_TOOL_RESULT_12345", "section": "test"}]
    
    registry = ToolRegistry()
    registry.register(create_mock_tool(
        "document_search",
        "Search documents",
        tool_result,
    ))
    
    responses = [
        create_llm_response(
            thought="Need to search the document",
            action="document_search",
            action_input={"query": query},
        ),
        create_llm_response(
            thought="Found the information",
            final_answer="Here is the answer based on the search.",
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
    
    # PROPERTY: Tool invocation should be recorded in intermediate steps
    tool_steps = [s for s in response.intermediate_steps if s.action == "document_search"]
    assert len(tool_steps) > 0, "Should have at least one tool invocation step"
    
    # PROPERTY: Tool result should appear in observation
    for step in tool_steps:
        assert step.observation is not None, "Tool step should have observation"
        # The distinctive result should be in the observation
        assert "DISTINCTIVE_TOOL_RESULT_12345" in step.observation, (
            "Tool result should appear in observation"
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    query=st.text(min_size=1, max_size=100).filter(lambda x: x.strip() != ""),
    document_id=valid_id,
    user_id=valid_id,
    num_tool_calls=st.integers(min_value=1, max_value=3),
)
def test_multiple_tool_results_all_incorporated(
    query: str,
    document_id: str,
    user_id: str,
    num_tool_calls: int,
):
    """
    **Feature: generic-agentic-rag, Property 4: Tool Result Incorporation**
    
    For any agent execution with multiple tool calls, ALL tool results SHALL
    appear in the intermediate_steps.
    
    **Validates: Requirements 2.2**
    """
    registry = create_registry_with_tools()
    
    # Create responses with multiple tool calls
    responses = []
    for i in range(num_tool_calls):
        responses.append(create_llm_response(
            thought=f"Tool call {i+1}",
            action="document_search",
            action_input={"query": f"search {i+1}"},
        ))
    
    # Final answer
    responses.append(create_llm_response(
        thought="Have all information",
        final_answer="Final answer based on all searches.",
    ))
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=num_tool_calls + 5,
    )
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: All tool calls should have observations
    tool_steps = [s for s in response.intermediate_steps if s.action is not None]
    
    assert len(tool_steps) == num_tool_calls, (
        f"Expected {num_tool_calls} tool steps, got {len(tool_steps)}"
    )
    
    for i, step in enumerate(tool_steps):
        assert step.observation is not None, (
            f"Tool step {i+1} should have observation"
        )


# =============================================================================
# Property 7: Complex Query Decomposition
# =============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    question_parts=complex_question_parts,
    document_id=valid_id,
    user_id=valid_id,
)
def test_complex_query_produces_multiple_steps(
    question_parts: List[str],
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 7: Complex Query Decomposition**
    
    For any complex multi-part question, the agent SHALL produce at least 2
    intermediate reasoning steps before the final answer.
    
    **Validates: Requirements 3.1**
    """
    assume(len(question_parts) >= 2)
    
    # Create a complex multi-part question
    complex_query = " and ".join(question_parts)
    
    registry = create_registry_with_tools()
    
    # Create responses that decompose the query into multiple steps
    num_steps = len(question_parts)
    responses = []
    
    for i, part in enumerate(question_parts):
        responses.append(create_llm_response(
            thought=f"Addressing part {i+1}: {part[:20]}...",
            action="document_search",
            action_input={"query": part},
        ))
    
    # Final synthesis
    responses.append(create_llm_response(
        thought="Synthesizing all parts into final answer",
        final_answer=f"Comprehensive answer addressing all {num_steps} parts.",
    ))
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=num_steps + 5,
    )
    
    with patch.object(agent, '_call_llm', side_effect=mock_responder):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=complex_query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Complex queries should produce at least 2 intermediate steps
    assert len(response.intermediate_steps) >= 2, (
        f"Complex query should produce at least 2 steps, got {len(response.intermediate_steps)}"
    )
    
    # PROPERTY: Final answer should be synthesized
    assert response.answer is not None
    assert response.answer != ""


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    document_id=valid_id,
    user_id=valid_id,
)
def test_complex_query_with_explicit_parts(
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 7: Complex Query Decomposition**
    
    For a query with explicit multiple parts (e.g., "First... Second... Third..."),
    the agent SHALL address each part in its reasoning.
    
    **Validates: Requirements 3.1**
    """
    # Explicit multi-part query
    complex_query = "First, what is the main topic? Second, who are the key figures? Third, what are the conclusions?"
    
    registry = create_registry_with_tools()
    
    # Responses that address each part
    responses = [
        create_llm_response(
            thought="Addressing first part: main topic",
            action="document_search",
            action_input={"query": "main topic"},
        ),
        create_llm_response(
            thought="Addressing second part: key figures",
            action="document_search",
            action_input={"query": "key figures"},
        ),
        create_llm_response(
            thought="Addressing third part: conclusions",
            action="document_search",
            action_input={"query": "conclusions"},
        ),
        create_llm_response(
            thought="Synthesizing all three parts",
            final_answer="1. Main topic is X. 2. Key figures are Y. 3. Conclusions are Z.",
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
            agent.run(query=complex_query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Should have multiple reasoning steps
    assert len(response.intermediate_steps) >= 2, (
        "Multi-part query should produce multiple reasoning steps"
    )
    
    # PROPERTY: Each step should have a thought
    for step in response.intermediate_steps:
        assert step.thought is not None
        assert step.thought != ""


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    document_id=valid_id,
    user_id=valid_id,
)
def test_complex_query_maintains_context_across_steps(
    document_id: str,
    user_id: str,
):
    """
    **Feature: generic-agentic-rag, Property 7: Complex Query Decomposition**
    
    For complex queries, information from earlier steps SHALL be available
    in later steps (context preservation during decomposition).
    
    **Validates: Requirements 3.1**
    """
    complex_query = "What is the relationship between concept A and concept B?"
    
    registry = create_registry_with_tools()
    
    responses = [
        create_llm_response(
            thought="First, I need to understand concept A",
            action="document_search",
            action_input={"query": "concept A"},
        ),
        create_llm_response(
            thought="Now I understand A. Next, I need to understand concept B",
            action="document_search",
            action_input={"query": "concept B"},
        ),
        create_llm_response(
            thought="I now understand both A and B. I can explain their relationship.",
            final_answer="The relationship between A and B is...",
        ),
    ]
    
    mock_responder = MockLLMResponder(responses)
    
    agent = ReActAgent(
        tool_registry=registry,
        router=None,
        max_steps=10,
    )
    
    # Track conversation history growth
    history_lengths = []
    
    def tracking_call_llm(messages):
        history_lengths.append(len(messages))
        return mock_responder(messages)
    
    with patch.object(agent, '_call_llm', side_effect=tracking_call_llm):
        response = asyncio.get_event_loop().run_until_complete(
            agent.run(query=complex_query, document_id=document_id, user_id=user_id)
        )
    
    # PROPERTY: Conversation history should grow with each step
    # (indicating context is being preserved)
    for i in range(1, len(history_lengths)):
        assert history_lengths[i] >= history_lengths[i-1], (
            f"History should grow: step {i} has {history_lengths[i]} messages, "
            f"step {i-1} had {history_lengths[i-1]}"
        )
    
    # PROPERTY: Final answer should be produced
    assert response.answer is not None
    assert response.answer != ""
