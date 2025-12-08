"""
Retrieval module for hybrid search.

Contains:
- Unified tokenizer for BM25 indexing and querying
- BM25 search implementation
- BM25 index persistence store
- Index manager for dual-store transactions
- Hybrid retriever combining vector and BM25 search
- RRF (Reciprocal Rank Fusion) algorithm
"""

from .tokenizer import (
    tokenize,
    is_chinese_text,
)
from .bm25_service import (
    BM25Service,
    BM25SearchResult,
    ChunkData,
)
from .bm25_store import (
    BM25IndexStore,
    BM25IndexData,
)
from .index_manager import (
    IndexManager,
    IndexDocumentRequest,
    IndexResult,
    DeleteResult,
    VectorStoreProtocol,
)
from .hybrid_retriever import (
    HybridRetriever,
    RetrievalResult,
)

__all__ = [
    "tokenize",
    "is_chinese_text",
    "BM25Service",
    "BM25SearchResult",
    "ChunkData",
    "BM25IndexStore",
    "BM25IndexData",
    "IndexManager",
    "IndexDocumentRequest",
    "IndexResult",
    "DeleteResult",
    "VectorStoreProtocol",
    "HybridRetriever",
    "RetrievalResult",
]
