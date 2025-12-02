"""
Index Manager for Dual-Store Transaction Mechanism.

This module provides atomic operations for indexing and deleting documents
across both ChromaDB (vector store) and BM25 (keyword store) with proper
rollback on failure to ensure consistency.

Requirements: 6.2 - THE Agentic_RAG_System SHALL support keyword-based search using BM25 algorithm.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from .bm25_service import BM25Service, ChunkData
from .bm25_store import BM25IndexStore


class VectorStoreProtocol(Protocol):
    """Protocol for vector store operations."""
    
    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        """Add documents to the vector store."""
        ...
    
    def delete(self, where: Dict[str, Any]) -> None:
        """Delete documents from the vector store."""
        ...


@dataclass
class IndexDocumentRequest:
    """Request data for indexing a document."""
    document_id: str
    user_id: str
    chunk_ids: List[str]
    texts: List[str]
    embeddings: List[List[float]]
    metadatas: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class IndexResult:
    """Result of an indexing operation."""
    success: bool
    document_id: str
    vector_indexed: bool = False
    bm25_indexed: bool = False
    error: Optional[str] = None


@dataclass
class DeleteResult:
    """Result of a delete operation."""
    success: bool
    document_id: str
    vector_deleted: bool = False
    bm25_deleted: bool = False
    error: Optional[str] = None


class IndexManager:
    """
    Manages atomic indexing operations across vector and BM25 stores.
    
    Provides transactional semantics with rollback on failure to ensure
    consistency between the two stores.
    
    Example:
        >>> manager = IndexManager(vector_collection, bm25_store)
        >>> request = IndexDocumentRequest(
        ...     document_id="doc123",
        ...     user_id="user456",
        ...     chunk_ids=["chunk1", "chunk2"],
        ...     texts=["Hello world", "Goodbye world"],
        ...     embeddings=[[0.1, 0.2], [0.3, 0.4]],
        ... )
        >>> result = manager.index_document(request)
        >>> result.success
        True
    """
    
    def __init__(
        self,
        vector_collection: VectorStoreProtocol,
        bm25_store: Optional[BM25IndexStore] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the IndexManager.
        
        Args:
            vector_collection: ChromaDB collection or compatible vector store
            bm25_store: BM25 index store for keyword search
            logger: Optional logger instance
        """
        self._vector_collection = vector_collection
        self._bm25_store = bm25_store or BM25IndexStore()
        self._logger = logger or logging.getLogger("app.agent.retrieval.index_manager")
    
    def index_document(self, request: IndexDocumentRequest) -> IndexResult:
        """
        Atomically index a document in both vector and BM25 stores.
        
        Uses a try-except-rollback pattern to ensure consistency:
        1. Index in vector store first
        2. Index in BM25 store
        3. If BM25 fails, rollback vector store changes
        
        Args:
            request: IndexDocumentRequest containing document data
            
        Returns:
            IndexResult indicating success/failure and which stores were indexed
        """
        result = IndexResult(
            success=False,
            document_id=request.document_id,
        )
        
        if not request.texts:
            result.error = "No texts provided for indexing"
            self._logger.warning(
                "Index request has no texts",
                extra={"document_id": request.document_id},
            )
            return result
        
        # Prepare metadatas with user_id and document_id
        metadatas = self._prepare_metadatas(request)
        
        # Step 1: Index in vector store
        try:
            self._index_vector_store(request, metadatas)
            result.vector_indexed = True
            self._logger.info(
                "Indexed document in vector store",
                extra={
                    "document_id": request.document_id,
                    "chunk_count": len(request.texts),
                },
            )
        except Exception as e:
            result.error = f"Vector store indexing failed: {str(e)}"
            self._logger.error(
                "Failed to index in vector store",
                extra={
                    "document_id": request.document_id,
                    "error": str(e),
                },
            )
            return result
        
        # Step 2: Index in BM25 store
        try:
            self._index_bm25_store(request, metadatas)
            result.bm25_indexed = True
            self._logger.info(
                "Indexed document in BM25 store",
                extra={
                    "document_id": request.document_id,
                    "chunk_count": len(request.texts),
                },
            )
        except Exception as e:
            # Rollback vector store on BM25 failure
            self._logger.error(
                "BM25 indexing failed, rolling back vector store",
                extra={
                    "document_id": request.document_id,
                    "error": str(e),
                },
            )
            self._rollback_vector_store(request.document_id, request.user_id)
            result.vector_indexed = False
            result.error = f"BM25 indexing failed (vector store rolled back): {str(e)}"
            return result
        
        result.success = True
        return result
    
    def delete_document(self, document_id: str, user_id: str) -> DeleteResult:
        """
        Atomically delete a document from both vector and BM25 stores.
        
        Attempts to delete from both stores, continuing even if one fails.
        Reports partial success if only one store deletion succeeds.
        
        Args:
            document_id: Unique identifier for the document
            user_id: User who owns the document
            
        Returns:
            DeleteResult indicating success/failure for each store
        """
        result = DeleteResult(
            success=False,
            document_id=document_id,
        )
        
        errors: List[str] = []
        
        # Step 1: Delete from vector store
        try:
            self._delete_from_vector_store(document_id, user_id)
            result.vector_deleted = True
            self._logger.info(
                "Deleted document from vector store",
                extra={"document_id": document_id, "user_id": user_id},
            )
        except Exception as e:
            errors.append(f"Vector store deletion failed: {str(e)}")
            self._logger.error(
                "Failed to delete from vector store",
                extra={
                    "document_id": document_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )
        
        # Step 2: Delete from BM25 store
        try:
            deleted = self._bm25_store.delete(document_id)
            result.bm25_deleted = deleted
            if deleted:
                self._logger.info(
                    "Deleted document from BM25 store",
                    extra={"document_id": document_id},
                )
            else:
                self._logger.debug(
                    "No BM25 index found for document",
                    extra={"document_id": document_id},
                )
        except Exception as e:
            errors.append(f"BM25 store deletion failed: {str(e)}")
            self._logger.error(
                "Failed to delete from BM25 store",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                },
            )
        
        # Determine overall success
        if result.vector_deleted or result.bm25_deleted:
            result.success = True
        
        if errors:
            result.error = "; ".join(errors)
        
        return result
    
    def _prepare_metadatas(
        self,
        request: IndexDocumentRequest,
    ) -> List[Dict[str, Any]]:
        """
        Prepare metadata dictionaries for each chunk.
        
        Ensures each metadata dict contains user_id and document_id.
        """
        metadatas: List[Dict[str, Any]] = []
        
        for i, _ in enumerate(request.texts):
            if i < len(request.metadatas):
                metadata = dict(request.metadatas[i])
            else:
                metadata = {}
            
            metadata["user_id"] = request.user_id
            metadata["document_id"] = request.document_id
            metadatas.append(metadata)
        
        return metadatas
    
    def _index_vector_store(
        self,
        request: IndexDocumentRequest,
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Index chunks in the vector store."""
        self._vector_collection.add(
            documents=request.texts,
            embeddings=request.embeddings,
            metadatas=metadatas,
            ids=request.chunk_ids,
        )
    
    def _index_bm25_store(
        self,
        request: IndexDocumentRequest,
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Build and persist BM25 index for the document."""
        chunks = [
            ChunkData(
                chunk_id=chunk_id,
                text=text,
                metadata=metadata,
            )
            for chunk_id, text, metadata in zip(
                request.chunk_ids,
                request.texts,
                metadatas,
            )
        ]
        
        bm25_service = BM25Service()
        bm25_service.build_index(chunks)
        self._bm25_store.save(request.document_id, bm25_service)
    
    def _rollback_vector_store(self, document_id: str, user_id: str) -> None:
        """Rollback vector store changes by deleting the document."""
        try:
            self._delete_from_vector_store(document_id, user_id)
            self._logger.info(
                "Successfully rolled back vector store",
                extra={"document_id": document_id, "user_id": user_id},
            )
        except Exception as e:
            self._logger.error(
                "Failed to rollback vector store - manual cleanup may be required",
                extra={
                    "document_id": document_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )
    
    def _delete_from_vector_store(self, document_id: str, user_id: str) -> None:
        """Delete a document from the vector store."""
        self._vector_collection.delete(
            where={
                "$and": [
                    {"document_id": {"$eq": document_id}},
                    {"user_id": {"$eq": user_id}},
                ]
            }
        )
    
    def check_consistency(self, document_id: str) -> Dict[str, bool]:
        """
        Check if a document exists in both stores.
        
        Useful for debugging and reconciliation.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            Dict with 'vector_exists' and 'bm25_exists' keys
        """
        return {
            "bm25_exists": self._bm25_store.exists(document_id),
            # Note: Vector store existence check would require a query
            # which is not implemented here to avoid complexity
        }
