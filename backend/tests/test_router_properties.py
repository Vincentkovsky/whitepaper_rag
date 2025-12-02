import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for Intent Router.

**Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
"""

from datetime import timedelta
from typing import List
from hypothesis import given, strategies as st, settings, assume

from app.agent.router import IntentRouter
from app.agent.types import IntentType


# Increase deadline for tests that may involve initialization overhead
EXTENDED_DEADLINE = timedelta(seconds=5)


# =============================================================================
# Test Data: Known small-talk and greeting patterns
# =============================================================================

# English greetings that should be classified as DIRECT_ANSWER
ENGLISH_GREETINGS: List[str] = [
    "hi",
    "hello",
    "hey",
    "howdy",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "how are you",
    "what's up",
    "how's it going",
    "nice to meet you",
]

# Chinese greetings that should be classified as DIRECT_ANSWER
CHINESE_GREETINGS: List[str] = [
    "你好",
    "您好",
    "嗨",
    "哈喽",
    "早上好",
    "下午好",
    "晚上好",
    "晚安",
    "你好吗",
    "最近怎么样",
    "在吗",
]

# English small-talk that should be classified as DIRECT_ANSWER
ENGLISH_SMALL_TALK: List[str] = [
    "thanks",
    "thank you",
    "thx",
    "bye",
    "goodbye",
    "see you",
    "later",
    "yes",
    "no",
    "ok",
    "okay",
    "sure",
    "alright",
    "please",
    "sorry",
    "excuse me",
    "who are you",
    "what can you do",
    "help",
]

# Chinese small-talk that should be classified as DIRECT_ANSWER
CHINESE_SMALL_TALK: List[str] = [
    "谢谢",
    "感谢",
    "再见",
    "拜拜",
    "好",
    "好的",
    "是",
    "是的",
    "不",
    "不是",
    "你是谁",
    "你能做什么",
    "帮助",
]

# All small-talk and greetings combined
ALL_SMALL_TALK = ENGLISH_GREETINGS + CHINESE_GREETINGS + ENGLISH_SMALL_TALK + CHINESE_SMALL_TALK


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for small-talk queries with optional punctuation/whitespace
small_talk_query = st.sampled_from(ALL_SMALL_TALK).flatmap(
    lambda base: st.tuples(
        st.just(base),
        st.sampled_from(["", " ", "  "]),  # Leading whitespace
        st.sampled_from(["", " ", "  "]),  # Trailing whitespace
        st.sampled_from(["", "!", "?", ".", "。", "！", "？"]),  # Punctuation
    ).map(lambda t: f"{t[1]}{t[0]}{t[3]}{t[2]}")
)


# =============================================================================
# Property 6: Router Small-Talk Bypass
# =============================================================================

@settings(max_examples=100, deadline=EXTENDED_DEADLINE)
@given(query=small_talk_query)
def test_router_small_talk_bypass_pattern_matching(query: str):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    For any small-talk or greeting query (e.g., "你好", "hello", "how are you"),
    the Router SHALL classify it as DIRECT_ANSWER and no document/web search
    tools SHALL be invoked.
    
    This test verifies the pattern-matching path (no LLM needed).
    
    **Validates: Requirements 2.6**
    """
    # Create router without LLM client (pattern matching only)
    router = IntentRouter(openai_client=None)
    
    # Classify the query
    result = router.classify(query)
    
    # PROPERTY: Small-talk should be classified as DIRECT_ANSWER
    assert result.intent == IntentType.DIRECT_ANSWER, (
        f"Query '{query}' should be classified as DIRECT_ANSWER, "
        f"but got {result.intent.value} with reasoning: {result.reasoning}"
    )
    
    # PROPERTY: Confidence should be high for pattern-matched queries
    assert result.confidence >= 0.9, (
        f"Pattern-matched small-talk should have high confidence (>=0.9), "
        f"but got {result.confidence}"
    )


@settings(max_examples=100, deadline=EXTENDED_DEADLINE)
@given(greeting=st.sampled_from(ENGLISH_GREETINGS + CHINESE_GREETINGS))
def test_router_greeting_detection(greeting: str):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    For any greeting in English or Chinese, the Router SHALL classify it
    as DIRECT_ANSWER.
    
    **Validates: Requirements 2.6**
    """
    router = IntentRouter(openai_client=None)
    
    result = router.classify(greeting)
    
    # PROPERTY: Greetings should be DIRECT_ANSWER
    assert result.intent == IntentType.DIRECT_ANSWER, (
        f"Greeting '{greeting}' should be DIRECT_ANSWER, got {result.intent.value}"
    )
    
    # PROPERTY: is_small_talk convenience method should return True
    assert router.is_small_talk(greeting), (
        f"is_small_talk('{greeting}') should return True"
    )


@settings(max_examples=100, deadline=EXTENDED_DEADLINE)
@given(small_talk=st.sampled_from(ENGLISH_SMALL_TALK + CHINESE_SMALL_TALK))
def test_router_small_talk_detection(small_talk: str):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    For any small-talk phrase in English or Chinese, the Router SHALL
    classify it as DIRECT_ANSWER.
    
    **Validates: Requirements 2.6**
    """
    router = IntentRouter(openai_client=None)
    
    result = router.classify(small_talk)
    
    # PROPERTY: Small-talk should be DIRECT_ANSWER
    assert result.intent == IntentType.DIRECT_ANSWER, (
        f"Small-talk '{small_talk}' should be DIRECT_ANSWER, got {result.intent.value}"
    )
    
    # PROPERTY: is_small_talk convenience method should return True
    assert router.is_small_talk(small_talk), (
        f"is_small_talk('{small_talk}') should return True"
    )


@settings(max_examples=100, deadline=EXTENDED_DEADLINE)
@given(
    base_query=st.sampled_from(ALL_SMALL_TALK),
    case_variant=st.sampled_from(["lower", "upper", "title", "original"])
)
def test_router_case_insensitive_small_talk(base_query: str, case_variant: str):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    For any small-talk query in any case variation (upper, lower, title),
    the Router SHALL classify it as DIRECT_ANSWER.
    
    **Validates: Requirements 2.6**
    """
    # Apply case transformation
    if case_variant == "lower":
        query = base_query.lower()
    elif case_variant == "upper":
        query = base_query.upper()
    elif case_variant == "title":
        query = base_query.title()
    else:
        query = base_query
    
    router = IntentRouter(openai_client=None)
    result = router.classify(query)
    
    # PROPERTY: Case variations should still be DIRECT_ANSWER
    assert result.intent == IntentType.DIRECT_ANSWER, (
        f"Query '{query}' (case: {case_variant}) should be DIRECT_ANSWER, "
        f"got {result.intent.value}"
    )


# =============================================================================
# Property: Non-small-talk queries should NOT be classified as DIRECT_ANSWER
# =============================================================================

# Document-related queries that should NOT be small-talk
DOCUMENT_QUERIES: List[str] = [
    "What is the main topic of this document?",
    "Summarize the key points",
    "这篇文档讲了什么?",
    "文档的主要内容是什么?",
    "Explain the methodology used",
    "What are the conclusions?",
    "How does this compare to other approaches?",
    "What data was used in the analysis?",
]


@settings(max_examples=100, deadline=None)  # Disable deadline - LLM calls may timeout and fallback
@given(query=st.sampled_from(DOCUMENT_QUERIES))
def test_router_document_queries_not_small_talk(query: str):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    For any document-related query, the Router SHALL NOT classify it as
    DIRECT_ANSWER via pattern matching (it should go to LLM classification
    or default to DOCUMENT_QA).
    
    **Validates: Requirements 2.6**
    """
    # Create router - it may try LLM classification which could timeout,
    # but the fallback should return DOCUMENT_QA with low confidence
    router = IntentRouter(openai_client=None)
    
    # PROPERTY: Document queries should NOT match small-talk patterns
    assert not router.is_small_talk(query), (
        f"Document query '{query}' should NOT be detected as small-talk"
    )
    
    # When no LLM is available, non-small-talk queries should default to DOCUMENT_QA
    # (the LLM path will fail and fall back to DOCUMENT_QA with low confidence)
    result = router.classify(query)
    
    # The key property: document queries should NOT be classified as high-confidence DIRECT_ANSWER
    # They should either be DOCUMENT_QA or low-confidence DIRECT_ANSWER (which gets escalated)
    assert result.intent == IntentType.DOCUMENT_QA or result.confidence < 0.8, (
        f"Document query '{query}' should be DOCUMENT_QA or low-confidence, "
        f"got {result.intent.value} with confidence {result.confidence}"
    )


# =============================================================================
# Property: Confidence threshold fallback mechanism
# =============================================================================

def test_router_confidence_threshold_fallback():
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    When DIRECT_ANSWER confidence is below the threshold (0.8),
    the Router SHALL escalate to DOCUMENT_QA to avoid false negatives.
    
    **Validates: Requirements 2.6**
    """
    # Create router with custom threshold
    router = IntentRouter(openai_client=None, confidence_threshold=0.8)
    
    # Verify the threshold is set correctly
    assert router.confidence_threshold == 0.8
    
    # Pattern-matched queries should have high confidence and NOT be escalated
    result = router.classify("hello")
    assert result.intent == IntentType.DIRECT_ANSWER
    assert result.confidence >= 0.8  # Should not trigger fallback


@settings(max_examples=50, deadline=EXTENDED_DEADLINE)
@given(threshold=st.floats(min_value=0.5, max_value=0.99))
def test_router_configurable_threshold(threshold: float):
    """
    **Feature: generic-agentic-rag, Property 6: Router Small-Talk Bypass**
    
    The Router SHALL support configurable confidence thresholds.
    
    **Validates: Requirements 2.6**
    """
    router = IntentRouter(openai_client=None, confidence_threshold=threshold)
    
    # PROPERTY: Threshold should be configurable
    assert router.confidence_threshold == threshold
    
    # Pattern-matched queries should still work regardless of threshold
    result = router.classify("hello")
    assert result.intent == IntentType.DIRECT_ANSWER
