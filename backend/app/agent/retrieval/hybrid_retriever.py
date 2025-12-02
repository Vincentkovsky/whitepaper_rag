"""
Hybrid Retriever combining vector search and BM25 keyword search.

This module implements hybrid retrieval using:
- Vector-based semantic search via ChromaDB
- Keyword-based search via BM25
- Reciprocal Rank Fusion (RRF) for result combination

Requirements:
- 6.1: THE Agentic_RAG_System SHALL support vector-based semantic search using embeddings.
- 6.2: THE Agentic_RAG_System SHALL support keyword-based search using BM25 algorithm.
- 6.3: WHEN performing a search, THE Agentic_RAG_System SHALL combine results from both
       vector and keyword search using Reciprocal Rank Fusion (RRF) algorithm.
- 6.4: THE Agentic_RAG_System SHALL allow configuration of the weight ratio between
       vector and keyword search results with a default of 0.7:0.3.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chromadb

from .bm25_service import BM25Service, BM25SearchResult
from .bm25_store import BM25IndexStore


logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """
    Result from hybrid retrieval.
    
    Contains the chunk data along with scores from both retrieval methods
    and the final fused score.
    """
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    fused_score: float = 0.0


class HybridRetriever:
    """
    Hybrid retriever combining vector search and BM25 keyword search.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results from both
    retrieval methods into a single ranked list.
    
    The RRF formula is:
        RRF(d) = sum(1 / (k + rank(d))) for each ranking
    
    Where k is a constant (default 60) that controls the impact of
    lower-ranked documents.
    
    Example:
        >>> retriever = HybridRetriever(chroma_client, bm25_store)
        >>> results = retriever.search(
        ...     query="What is Bitcoin?",
        ...     document_id="doc123",
        ...     user_id="user456",
        ...     k=10,
        ... )
        >>> for r in results:
        ...     print(f"{r.chunk_id}: {r.fused_score:.4f}")
    """
    
    # Default RRF constant - controls impact of lower-ranked documents
    DEFAULT_RRF_K = 60
    
    def __init__(
        self,
        chroma_client: chromadb.Client,
        bm25_store: Optional[BM25IndexStore] = None,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        rrf_k: int = DEFAULT_RRF_K,
        collection_name: str = "documents",
    ) -> None:
        """
        Initialize the hybrid retriever.
        
        Args:
            chroma_client: ChromaDB client for vector search
            bm25_store: BM25 index store for keyword search (optional)
            vector_weight: Weight for vector search results (default 0.7)
            bm25_weight: Weight for BM25 search results (default 0.3)
            rrf_k: RRF constant k (default 60)
            collection_name: Name of the ChromaDB collection
        """
        self._chroma = chroma_client
        self._bm25_store = bm25_store or BM25IndexStore()
        self._vector_weight = vector_weight
        self._bm25_weight = bm25_weight
        self._rrf_k = rrf_k
        self._collection_name = collection_name
        
        # Get or create the collection
        self._collection = self._chroma.get_or_create_collection(collection_name)
    
    @property
    def vector_weight(self) -> float:
        """Get the vector search weight."""
        return self._vector_weight
    
    @vector_weight.setter
    def vector_weight(self, value: float) -> None:
        """Set the vector search weight."""
        if not 0.0 <= value <= 1.0:
            raise ValueError("vector_weight must be between 0.0 and 1.0")
        self._vector_weight = value
    
    @property
    def bm25_weight(self) -> float:
        """Get the BM25 search weight."""
        return self._bm25_weight
    
    @bm25_weight.setter
    def bm25_weight(self, value: float) -> None:
        """Set the BM25 search weight."""
        if not 0.0 <= value <= 1.0:
            raise ValueError("bm25_weight must be between 0.0 and 1.0")
        self._bm25_weight = value
    
    @property
    def rrf_k(self) -> int:
        """Get the RRF k constant."""
        return self._rrf_k
    
    def search(
        self,
        query: str,
        document_id: str,
        user_id: str,
        query_embedding: List[float],
        k: int = 10,
    ) -> List[RetrievalResult]:
        """
        Perform hybrid search combining vector and BM25 results.
        
        Args:
            query: The search query string
            document_id: ID of the document to search within
            user_id: ID of the user who owns the document
            query_embedding: Pre-computed embedding for the query
            k: Maximum number of results to return
            
        Returns:
            List of RetrievalResult objects sorted by fused score (descending)
        """
        # Perform vector search
        vector_results = self._vector_search(
            query_embedding=query_embedding,
            document_id=document_id,
            user_id=user_id,
            k=k * 2,  # Fetch more for better fusion
        )
        
        # Perform BM25 search
        bm25_results = self._bm25_search(
            query=query,
            document_id=document_id,
            k=k * 2,
        )
        
        # If BM25 returns no results, fall back to vector-only
        # Requirement 6.5: IF keyword search returns no results, THEN THE
        # Agentic_RAG_System SHALL fall back to vector-only search.
        if not bm25_results:
            logger.info(
                "BM25 returned no results, falling back to vector-only search",
                extra={"document_id": document_id},
            )
            return vector_results[:k]
        
        # Fuse results using RRF
        fused_results = self._rrf_fusion(vector_results, bm25_results)
        
        return fused_results[:k]
    
    def _vector_search(
        self,
        query_embedding: List[float],
        document_id: str,
        user_id: str,
        k: int,
    ) -> List[RetrievalResult]:
        """
        Perform vector search using ChromaDB.
        
        Args:
            query_embedding: The query embedding vector
            document_id: ID of the document to search within
            user_id: ID of the user who owns the document
            k: Maximum number of results
            
        Returns:
            List of RetrievalResult objects with vector_score populated
        """
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                where={
                    "$and": [
                        {"user_id": {"$eq": user_id}},
                        {"document_id": {"$eq": document_id}},
                    ]
                },
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}", extra={"document_id": document_id})
            return []
        
        retrieval_results: List[RetrievalResult] = []
        
        if not results["ids"] or not results["ids"][0]:
            return retrieval_results
        
        for idx in range(len(results["ids"][0])):
            # ChromaDB returns distances, convert to similarity score
            # Lower distance = higher similarity
            distance = results["distances"][0][idx]
            # Convert distance to a score (1 / (1 + distance))
            vector_score = 1.0 / (1.0 + distance)
            
            retrieval_results.append(RetrievalResult(
                chunk_id=results["ids"][0][idx],
                text=results["documents"][0][idx],
                metadata=results["metadatas"][0][idx] if results["metadatas"] else {},
                vector_score=vector_score,
                bm25_score=None,
                fused_score=vector_score,  # Initial score before fusion
            ))
        
        return retrieval_results
    
    def _bm25_search(
        self,
        query: str,
        document_id: str,
        k: int,
    ) -> List[RetrievalResult]:
        """
        Perform BM25 keyword search.
        
        Args:
            query: The search query string
            document_id: ID of the document to search within
            k: Maximum number of results
            
        Returns:
            List of RetrievalResult objects with bm25_score populated
        """
        # Load the BM25 index for this document
        bm25_service = self._bm25_store.load(document_id)
        
        if bm25_service is None:
            logger.warning(
                f"No BM25 index found for document {document_id}",
                extra={"document_id": document_id},
            )
            return []
        
        try:
            bm25_results: List[BM25SearchResult] = bm25_service.search(query, k=k)
        except Exception as e:
            logger.error(f"BM25 search failed: {e}", extra={"document_id": document_id})
            return []
        
        retrieval_results: List[RetrievalResult] = []
        
        for result in bm25_results:
            retrieval_results.append(RetrievalResult(
                chunk_id=result.chunk_id,
                text=result.text,
                metadata=result.metadata,
                vector_score=None,
                bm25_score=result.score,
                fused_score=result.score,  # Initial score before fusion
            ))
        
        return retrieval_results
    
    def _rrf_fusion(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """
        Apply Reciprocal Rank Fusion to combine results from both methods.
        
        The RRF formula is:
            RRF(d) = w_v * (1 / (k + rank_v(d))) + w_b * (1 / (k + rank_b(d)))
        
        Where:
            - w_v is the vector weight
            - w_b is the BM25 weight
            - k is the RRF constant
            - rank_v(d) is the rank of document d in vector results (1-indexed)
            - rank_b(d) is the rank of document d in BM25 results (1-indexed)
        
        Args:
            vector_results: Results from vector search (already sorted by score)
            bm25_results: Results from BM25 search (already sorted by score)
            
        Returns:
            List of RetrievalResult objects sorted by fused score (descending)
        """
        # Build a map of chunk_id -> RetrievalResult for merging
        result_map: Dict[str, RetrievalResult] = {}
        
        # Process vector results and assign RRF scores
        for rank, result in enumerate(vector_results, start=1):
            rrf_score = self._vector_weight * (1.0 / (self._rrf_k + rank))
            
            if result.chunk_id not in result_map:
                result_map[result.chunk_id] = RetrievalResult(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    metadata=result.metadata,
                    vector_score=result.vector_score,
                    bm25_score=None,
                    fused_score=rrf_score,
                )
            else:
                result_map[result.chunk_id].vector_score = result.vector_score
                result_map[result.chunk_id].fused_score += rrf_score
        
        # Process BM25 results and add/update RRF scores
        for rank, result in enumerate(bm25_results, start=1):
            rrf_score = self._bm25_weight * (1.0 / (self._rrf_k + rank))
            
            if result.chunk_id not in result_map:
                result_map[result.chunk_id] = RetrievalResult(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    metadata=result.metadata,
                    vector_score=None,
                    bm25_score=result.bm25_score,
                    fused_score=rrf_score,
                )
            else:
                result_map[result.chunk_id].bm25_score = result.bm25_score
                result_map[result.chunk_id].fused_score += rrf_score
        
        # Sort by fused score descending
        fused_results = sorted(
            result_map.values(),
            key=lambda r: r.fused_score,
            reverse=True,
        )
        
        return fused_results
