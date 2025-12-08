"""
BM25 Index Service for keyword-based search.

This module provides BM25 indexing and search functionality using the rank_bm25 library.
It uses the unified tokenizer from tokenizer.py to ensure consistent tokenization
across both indexing and querying.

CRITICAL: This service MUST use the tokenize() function from tokenizer.py
for both index building and query processing to ensure consistency.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from .tokenizer import tokenize


@dataclass
class BM25SearchResult:
    """Result from a BM25 search query."""
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkData:
    """Data structure for a document chunk to be indexed."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BM25Service:
    """
    BM25 index service for keyword-based search.
    
    Uses rank_bm25's BM25Okapi implementation with the unified tokenizer
    to ensure consistent tokenization between indexing and querying.
    
    Example:
        >>> service = BM25Service()
        >>> chunks = [
        ...     ChunkData(chunk_id="1", text="Hello world"),
        ...     ChunkData(chunk_id="2", text="World peace"),
        ... ]
        >>> service.build_index(chunks)
        >>> results = service.search("hello", k=1)
        >>> results[0].chunk_id
        '1'
    """
    
    def __init__(self) -> None:
        """Initialize the BM25 service."""
        self._index: Optional[BM25Okapi] = None
        self._chunks: List[ChunkData] = []
        self._tokenized_corpus: List[List[str]] = []
    
    @property
    def is_indexed(self) -> bool:
        """Check if an index has been built."""
        return self._index is not None
    
    @property
    def chunk_count(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._chunks)
    
    def build_index(self, chunks: List[ChunkData]) -> None:
        """
        Build a BM25 index from a list of document chunks.
        
        Uses the unified tokenizer to tokenize each chunk's text.
        
        Args:
            chunks: List of ChunkData objects to index
            
        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            raise ValueError("Cannot build index from empty chunks list")
        
        self._chunks = chunks
        
        # Tokenize all chunks using the unified tokenizer
        self._tokenized_corpus = [
            tokenize(chunk.text) for chunk in chunks
        ]
        
        # Build the BM25 index
        self._index = BM25Okapi(self._tokenized_corpus)
    
    def search(
        self,
        query: str,
        k: int = 10,
        score_threshold: float = 0.0,
    ) -> List[BM25SearchResult]:
        """
        Search the BM25 index for relevant chunks.
        
        Uses the unified tokenizer to tokenize the query, ensuring
        consistency with the indexed documents.
        
        Args:
            query: Search query string
            k: Maximum number of results to return
            score_threshold: Minimum score threshold for results
            
        Returns:
            List of BM25SearchResult objects sorted by score (descending)
            
        Raises:
            RuntimeError: If no index has been built
        """
        if not self.is_indexed:
            raise RuntimeError("No index has been built. Call build_index() first.")
        
        if not query or not query.strip():
            return []
        
        # Tokenize query using the same tokenizer as indexing
        query_tokens = tokenize(query)
        
        if not query_tokens:
            return []
        
        # Get BM25 scores for all documents
        scores = self._index.get_scores(query_tokens)
        
        # Create (index, score) pairs and sort by score descending
        scored_indices: List[Tuple[int, float]] = [
            (i, score) for i, score in enumerate(scores)
            if score > score_threshold
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        
        # Take top k results
        top_results = scored_indices[:k]
        
        # Build result objects
        results = []
        for idx, score in top_results:
            chunk = self._chunks[idx]
            results.append(BM25SearchResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                score=score,
                metadata=chunk.metadata,
            ))
        
        return results
    
    def get_top_n(
        self,
        query: str,
        n: int = 10,
    ) -> List[BM25SearchResult]:
        """
        Get top N results for a query (alias for search with default threshold).
        
        Args:
            query: Search query string
            n: Number of results to return
            
        Returns:
            List of top N BM25SearchResult objects
        """
        return self.search(query, k=n)
    
    def get_index(self) -> Optional[BM25Okapi]:
        """
        Get the underlying BM25Okapi index object.
        
        Useful for serialization/persistence operations.
        
        Returns:
            The BM25Okapi index or None if not built
        """
        return self._index
    
    def get_chunks(self) -> List[ChunkData]:
        """
        Get the list of indexed chunks.
        
        Returns:
            List of ChunkData objects
        """
        return self._chunks.copy()
    
    def get_tokenized_corpus(self) -> List[List[str]]:
        """
        Get the tokenized corpus used for indexing.
        
        Returns:
            List of token lists for each chunk
        """
        return self._tokenized_corpus.copy()
    
    def clear(self) -> None:
        """Clear the index and all stored data."""
        self._index = None
        self._chunks = []
        self._tokenized_corpus = []
