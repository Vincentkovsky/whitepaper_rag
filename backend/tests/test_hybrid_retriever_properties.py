import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for Hybrid Retriever.

**Feature: generic-agentic-rag, Property 15: Hybrid Search Fusion**
**Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
"""

from typing import Any, Dict, List
from hypothesis import given, strategies as st, settings, assume
import tempfile
from pathlib import Path

from app.agent.retrieval.hybrid_retriever import HybridRetriever, RetrievalResult
from app.agent.retrieval.bm25_service import BM25Service, ChunkData, BM25SearchResult


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for generating valid chunk IDs
valid_chunk_id = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20
).filter(lambda x: x.strip() != "")

# Strategy for generating chunk text
valid_chunk_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=10,
    max_size=200
).filter(lambda x: x.strip() != "")

# Strategy for generating metadata
valid_metadata = st.fixed_dictionaries({
    "section": st.text(min_size=1, max_size=30).filter(lambda x: x.strip() != ""),
    "page": st.integers(min_value=1, max_value=100),
})

# Strategy for generating scores (positive floats)
valid_score = st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)

# Strategy for generating weights (between 0 and 1)
valid_weight = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def create_retrieval_result(
    chunk_id: str,
    text: str,
    metadata: Dict[str, Any],
    vector_score: float | None = None,
    bm25_score: float | None = None,
) -> RetrievalResult:
    """Helper to create a RetrievalResult."""
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        metadata=metadata,
        vector_score=vector_score,
        bm25_score=bm25_score,
        fused_score=vector_score or bm25_score or 0.0,
    )


# Strategy for generating a list of vector results
@st.composite
def vector_results_strategy(draw, min_size: int = 1, max_size: int = 10):
    """Generate a list of vector search results with unique chunk IDs."""
    num_results = draw(st.integers(min_value=min_size, max_value=max_size))
    chunk_ids = draw(st.lists(valid_chunk_id, min_size=num_results, max_size=num_results, unique=True))
    
    results = []
    for chunk_id in chunk_ids:
        text = draw(valid_chunk_text)
        metadata = draw(valid_metadata)
        score = draw(valid_score)
        results.append(create_retrieval_result(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
            vector_score=score,
        ))
    
    # Sort by score descending (as vector search would return)
    results.sort(key=lambda r: r.vector_score or 0, reverse=True)
    return results


@st.composite
def bm25_results_strategy(draw, min_size: int = 1, max_size: int = 10):
    """Generate a list of BM25 search results with unique chunk IDs."""
    num_results = draw(st.integers(min_value=min_size, max_value=max_size))
    chunk_ids = draw(st.lists(valid_chunk_id, min_size=num_results, max_size=num_results, unique=True))
    
    results = []
    for chunk_id in chunk_ids:
        text = draw(valid_chunk_text)
        metadata = draw(valid_metadata)
        score = draw(valid_score)
        results.append(create_retrieval_result(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
            bm25_score=score,
        ))
    
    # Sort by score descending (as BM25 search would return)
    results.sort(key=lambda r: r.bm25_score or 0, reverse=True)
    return results


# =============================================================================
# Property 15: Hybrid Search Fusion
# =============================================================================

@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=2, max_size=5),
    bm25_results=bm25_results_strategy(min_size=2, max_size=5),
    vector_weight=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
    rrf_k=st.integers(min_value=1, max_value=100),
)
def test_hybrid_search_fusion_contains_both_sources(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
    vector_weight: float,
    rrf_k: int,
):
    """
    **Feature: generic-agentic-rag, Property 15: Hybrid Search Fusion**
    
    For any search query against a document with indexed content, the hybrid
    search results SHALL contain items from both vector search and BM25 search
    (when both return results).
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    bm25_weight = 1.0 - vector_weight
    
    # Create a HybridRetriever with a mock ChromaDB client
    # We'll test the _rrf_fusion method directly since it's the core logic
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
        rrf_k=rrf_k,
    )
    
    # Call the RRF fusion method directly
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # PROPERTY: Fused results should contain chunks from both sources
    vector_chunk_ids = {r.chunk_id for r in vector_results}
    bm25_chunk_ids = {r.chunk_id for r in bm25_results}
    fused_chunk_ids = {r.chunk_id for r in fused_results}
    
    # All vector results should be in fused results
    assert vector_chunk_ids.issubset(fused_chunk_ids), \
        "All vector search results should be present in fused results"
    
    # All BM25 results should be in fused results
    assert bm25_chunk_ids.issubset(fused_chunk_ids), \
        "All BM25 search results should be present in fused results"
    
    # Total should be union of both (some may overlap)
    expected_total = vector_chunk_ids | bm25_chunk_ids
    assert fused_chunk_ids == expected_total, \
        "Fused results should contain exactly the union of both result sets"


@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=2, max_size=5),
    bm25_results=bm25_results_strategy(min_size=2, max_size=5),
    vector_weight=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
    rrf_k=st.integers(min_value=1, max_value=100),
)
def test_hybrid_search_fusion_follows_rrf_formula(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
    vector_weight: float,
    rrf_k: int,
):
    """
    **Feature: generic-agentic-rag, Property 15: Hybrid Search Fusion**
    
    For any hybrid search, the fused scores SHALL follow the RRF formula:
    RRF(d) = w_v * (1 / (k + rank_v(d))) + w_b * (1 / (k + rank_b(d)))
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    bm25_weight = 1.0 - vector_weight
    
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
        rrf_k=rrf_k,
    )
    
    # Call the RRF fusion method
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # Build rank maps for verification
    vector_ranks = {r.chunk_id: rank for rank, r in enumerate(vector_results, start=1)}
    bm25_ranks = {r.chunk_id: rank for rank, r in enumerate(bm25_results, start=1)}
    
    # PROPERTY: Each fused score should match the RRF formula
    for result in fused_results:
        expected_score = 0.0
        
        if result.chunk_id in vector_ranks:
            rank = vector_ranks[result.chunk_id]
            expected_score += vector_weight * (1.0 / (rrf_k + rank))
        
        if result.chunk_id in bm25_ranks:
            rank = bm25_ranks[result.chunk_id]
            expected_score += bm25_weight * (1.0 / (rrf_k + rank))
        
        # Allow small floating point tolerance
        assert abs(result.fused_score - expected_score) < 1e-9, \
            f"Fused score {result.fused_score} should match RRF formula result {expected_score}"


@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=3, max_size=6),
    bm25_results=bm25_results_strategy(min_size=3, max_size=6),
)
def test_hybrid_search_fusion_results_sorted_by_score(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
):
    """
    **Feature: generic-agentic-rag, Property 15: Hybrid Search Fusion**
    
    For any hybrid search, the fused results SHALL be sorted by fused score
    in descending order.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=0.7,
        bm25_weight=0.3,
    )
    
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # PROPERTY: Results should be sorted by fused_score descending
    scores = [r.fused_score for r in fused_results]
    assert scores == sorted(scores, reverse=True), \
        "Fused results should be sorted by score in descending order"


@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=2, max_size=5),
    bm25_results=bm25_results_strategy(min_size=2, max_size=5),
)
def test_hybrid_search_fusion_preserves_metadata(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
):
    """
    **Feature: generic-agentic-rag, Property 15: Hybrid Search Fusion**
    
    For any hybrid search, the fused results SHALL preserve the text and
    metadata from the original results.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=0.7,
        bm25_weight=0.3,
    )
    
    # Build lookup maps for original data
    original_data = {}
    for r in vector_results:
        original_data[r.chunk_id] = {"text": r.text, "metadata": r.metadata}
    for r in bm25_results:
        if r.chunk_id not in original_data:
            original_data[r.chunk_id] = {"text": r.text, "metadata": r.metadata}
    
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # PROPERTY: Each fused result should have correct text and metadata
    for result in fused_results:
        assert result.chunk_id in original_data, \
            f"Chunk {result.chunk_id} should be from original results"
        
        original = original_data[result.chunk_id]
        assert result.text == original["text"], \
            "Text should be preserved in fused results"
        assert result.metadata == original["metadata"], \
            "Metadata should be preserved in fused results"


# =============================================================================
# Property 16: Search Weight Configuration
# =============================================================================

@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=3, max_size=5),
    bm25_results=bm25_results_strategy(min_size=3, max_size=5),
    weight1=st.floats(min_value=0.1, max_value=0.4, allow_nan=False, allow_infinity=False),
    weight2=st.floats(min_value=0.6, max_value=0.9, allow_nan=False, allow_infinity=False),
)
def test_search_weight_configuration_affects_ranking(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
    weight1: float,
    weight2: float,
):
    """
    **Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
    
    For any two different weight configurations (vector_weight, bm25_weight),
    the same query SHALL produce different result rankings when the underlying
    scores differ.
    
    **Validates: Requirements 6.4**
    """
    # Ensure weights are meaningfully different
    assume(abs(weight1 - weight2) > 0.1)
    
    # The property only holds when rankings differ between vector and BM25.
    # When both result sets have identical chunk IDs in the same order,
    # the RRF formula simplifies to: score = (w_v + w_b) * (1/(k+rank)) = 1/(k+rank)
    # which is independent of weights. So we need rankings to differ.
    vector_chunk_order = [r.chunk_id for r in vector_results]
    bm25_chunk_order = [r.chunk_id for r in bm25_results]
    assume(vector_chunk_order != bm25_chunk_order)
    
    import chromadb
    chroma_client = chromadb.Client()
    
    # Create two retrievers with different weights
    retriever1 = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=weight1,
        bm25_weight=1.0 - weight1,
    )
    
    retriever2 = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=weight2,
        bm25_weight=1.0 - weight2,
    )
    
    # Get fused results from both
    fused1 = retriever1._rrf_fusion(vector_results, bm25_results)
    fused2 = retriever2._rrf_fusion(vector_results, bm25_results)
    
    # PROPERTY: The fused scores should be different for at least some results
    scores1 = {r.chunk_id: r.fused_score for r in fused1}
    scores2 = {r.chunk_id: r.fused_score for r in fused2}
    
    # At least one score should differ
    any_different = False
    for chunk_id in scores1:
        if chunk_id in scores2:
            if abs(scores1[chunk_id] - scores2[chunk_id]) > 1e-9:
                any_different = True
                break
    
    assert any_different, \
        "Different weight configurations should produce different fused scores"


@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=2, max_size=4),
    bm25_results=bm25_results_strategy(min_size=2, max_size=4),
)
def test_extreme_vector_weight_favors_vector_results(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
):
    """
    **Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
    
    When vector_weight is set to 1.0 (and bm25_weight to 0.0), the ranking
    SHALL be determined entirely by vector search ranks.
    
    **Validates: Requirements 6.4**
    """
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=1.0,
        bm25_weight=0.0,
    )
    
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # Get the chunk IDs that appear in vector results
    vector_chunk_ids = [r.chunk_id for r in vector_results]
    
    # PROPERTY: Vector-only chunks should be ranked by their vector rank
    # Filter fused results to only those in vector results
    fused_vector_only = [r for r in fused_results if r.chunk_id in vector_chunk_ids]
    
    # The order should match the original vector order
    fused_order = [r.chunk_id for r in fused_vector_only]
    
    # Check that vector results maintain their relative order
    for i, chunk_id in enumerate(vector_chunk_ids):
        if chunk_id in fused_order:
            # Find position in fused results
            fused_pos = fused_order.index(chunk_id)
            # All earlier vector results should also be earlier in fused
            for j in range(i):
                earlier_chunk = vector_chunk_ids[j]
                if earlier_chunk in fused_order:
                    earlier_fused_pos = fused_order.index(earlier_chunk)
                    assert earlier_fused_pos < fused_pos, \
                        "Vector results should maintain relative order with weight=1.0"


@settings(max_examples=100)
@given(
    vector_results=vector_results_strategy(min_size=2, max_size=4),
    bm25_results=bm25_results_strategy(min_size=2, max_size=4),
)
def test_extreme_bm25_weight_favors_bm25_results(
    vector_results: List[RetrievalResult],
    bm25_results: List[RetrievalResult],
):
    """
    **Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
    
    When bm25_weight is set to 1.0 (and vector_weight to 0.0), the ranking
    SHALL be determined entirely by BM25 search ranks.
    
    **Validates: Requirements 6.4**
    """
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=0.0,
        bm25_weight=1.0,
    )
    
    fused_results = retriever._rrf_fusion(vector_results, bm25_results)
    
    # Get the chunk IDs that appear in BM25 results
    bm25_chunk_ids = [r.chunk_id for r in bm25_results]
    
    # PROPERTY: BM25-only chunks should be ranked by their BM25 rank
    fused_bm25_only = [r for r in fused_results if r.chunk_id in bm25_chunk_ids]
    fused_order = [r.chunk_id for r in fused_bm25_only]
    
    # Check that BM25 results maintain their relative order
    for i, chunk_id in enumerate(bm25_chunk_ids):
        if chunk_id in fused_order:
            fused_pos = fused_order.index(chunk_id)
            for j in range(i):
                earlier_chunk = bm25_chunk_ids[j]
                if earlier_chunk in fused_order:
                    earlier_fused_pos = fused_order.index(earlier_chunk)
                    assert earlier_fused_pos < fused_pos, \
                        "BM25 results should maintain relative order with weight=1.0"


@settings(max_examples=100)
@given(
    vector_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_weight_setter_validation(vector_weight: float):
    """
    **Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
    
    The weight setters SHALL accept any value between 0.0 and 1.0.
    
    **Validates: Requirements 6.4**
    """
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=0.5,
        bm25_weight=0.5,
    )
    
    # Setting valid weights should work
    retriever.vector_weight = vector_weight
    assert retriever.vector_weight == vector_weight
    
    retriever.bm25_weight = vector_weight
    assert retriever.bm25_weight == vector_weight


@settings(max_examples=50)
@given(
    invalid_weight=st.floats().filter(lambda x: x < 0.0 or x > 1.0)
)
def test_weight_setter_rejects_invalid_values(invalid_weight: float):
    """
    **Feature: generic-agentic-rag, Property 16: Search Weight Configuration**
    
    The weight setters SHALL reject values outside the range [0.0, 1.0].
    
    **Validates: Requirements 6.4**
    """
    # Skip NaN and infinity
    assume(not (invalid_weight != invalid_weight))  # NaN check
    assume(abs(invalid_weight) != float('inf'))
    
    import chromadb
    chroma_client = chromadb.Client()
    
    retriever = HybridRetriever(
        chroma_client=chroma_client,
        vector_weight=0.5,
        bm25_weight=0.5,
    )
    
    # Setting invalid weights should raise ValueError
    try:
        retriever.vector_weight = invalid_weight
        assert False, f"Should have raised ValueError for weight {invalid_weight}"
    except ValueError:
        pass  # Expected
    
    try:
        retriever.bm25_weight = invalid_weight
        assert False, f"Should have raised ValueError for weight {invalid_weight}"
    except ValueError:
        pass  # Expected
