import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Tests for IndexManager dual-store transaction mechanism.

Tests the atomic indexing and deletion operations across vector and BM25 stores.
"""

import pytest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from app.agent.retrieval import (
    IndexManager,
    IndexDocumentRequest,
    IndexResult,
    DeleteResult,
    BM25IndexStore,
)


class MockVectorCollection:
    """Mock ChromaDB collection for testing."""
    
    def __init__(self, fail_on_add: bool = False, fail_on_delete: bool = False):
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.fail_on_add = fail_on_add
        self.fail_on_delete = fail_on_delete
        self.add_called = False
        self.delete_called = False
    
    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        self.add_called = True
        if self.fail_on_add:
            raise RuntimeError("Simulated vector store add failure")
        
        for i, doc_id in enumerate(ids):
            self.documents[doc_id] = {
                "document": documents[i],
                "embedding": embeddings[i],
                "metadata": metadatas[i],
            }
    
    def delete(self, where: Dict[str, Any]) -> None:
        self.delete_called = True
        if self.fail_on_delete:
            raise RuntimeError("Simulated vector store delete failure")
        
        # Extract document_id from where clause
        if "$and" in where:
            for condition in where["$and"]:
                if "document_id" in condition:
                    doc_id_prefix = condition["document_id"]["$eq"]
                    # Remove all documents with matching document_id
                    to_remove = [
                        k for k, v in self.documents.items()
                        if v.get("metadata", {}).get("document_id") == doc_id_prefix
                    ]
                    for k in to_remove:
                        del self.documents[k]


@pytest.fixture
def temp_bm25_dir():
    """Create a temporary directory for BM25 indexes."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def bm25_store(temp_bm25_dir):
    """Create a BM25IndexStore with temporary storage."""
    return BM25IndexStore(storage_path=temp_bm25_dir)


@pytest.fixture
def mock_vector_collection():
    """Create a mock vector collection."""
    return MockVectorCollection()


@pytest.fixture
def index_manager(mock_vector_collection, bm25_store):
    """Create an IndexManager with mock dependencies."""
    return IndexManager(
        vector_collection=mock_vector_collection,
        bm25_store=bm25_store,
    )


class TestIndexDocument:
    """Tests for index_document method."""
    
    def test_successful_indexing(self, index_manager, mock_vector_collection, bm25_store):
        """Test successful indexing in both stores."""
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1", "chunk2"],
            texts=["Hello world", "Goodbye world"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            metadatas=[{"source": "test"}, {"source": "test"}],
        )
        
        result = index_manager.index_document(request)
        
        assert result.success is True
        assert result.document_id == "doc123"
        assert result.vector_indexed is True
        assert result.bm25_indexed is True
        assert result.error is None
        
        # Verify vector store was updated
        assert mock_vector_collection.add_called
        assert len(mock_vector_collection.documents) == 2
        
        # Verify BM25 store was updated
        assert bm25_store.exists("doc123")
    
    def test_empty_texts_fails(self, index_manager):
        """Test that empty texts list fails gracefully."""
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=[],
            texts=[],
            embeddings=[],
        )
        
        result = index_manager.index_document(request)
        
        assert result.success is False
        assert result.error == "No texts provided for indexing"
        assert result.vector_indexed is False
        assert result.bm25_indexed is False
    
    def test_vector_store_failure(self, bm25_store):
        """Test handling of vector store failure."""
        failing_collection = MockVectorCollection(fail_on_add=True)
        manager = IndexManager(
            vector_collection=failing_collection,
            bm25_store=bm25_store,
        )
        
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1"],
            texts=["Hello world"],
            embeddings=[[0.1, 0.2]],
        )
        
        result = manager.index_document(request)
        
        assert result.success is False
        assert result.vector_indexed is False
        assert result.bm25_indexed is False
        assert "Vector store indexing failed" in result.error
        
        # BM25 should not be indexed
        assert not bm25_store.exists("doc123")
    
    def test_bm25_failure_triggers_rollback(self, mock_vector_collection, temp_bm25_dir):
        """Test that BM25 failure triggers vector store rollback."""
        # Create a BM25 store that will fail on save
        bm25_store = BM25IndexStore(storage_path=temp_bm25_dir)
        
        manager = IndexManager(
            vector_collection=mock_vector_collection,
            bm25_store=bm25_store,
        )
        
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1"],
            texts=["Hello world"],
            embeddings=[[0.1, 0.2]],
        )
        
        # Patch the BM25 store save to fail
        with patch.object(bm25_store, 'save', side_effect=RuntimeError("BM25 save failed")):
            result = manager.index_document(request)
        
        assert result.success is False
        assert result.vector_indexed is False  # Should be rolled back
        assert result.bm25_indexed is False
        assert "BM25 indexing failed" in result.error
        assert "rolled back" in result.error
        
        # Vector store should have been rolled back (delete called)
        assert mock_vector_collection.delete_called
    
    def test_metadata_preparation(self, index_manager, mock_vector_collection):
        """Test that metadata is properly prepared with user_id and document_id."""
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1"],
            texts=["Hello world"],
            embeddings=[[0.1, 0.2]],
            metadatas=[{"custom_field": "value"}],
        )
        
        result = index_manager.index_document(request)
        
        assert result.success is True
        
        # Check that metadata was enriched
        stored_doc = mock_vector_collection.documents["chunk1"]
        assert stored_doc["metadata"]["user_id"] == "user456"
        assert stored_doc["metadata"]["document_id"] == "doc123"
        assert stored_doc["metadata"]["custom_field"] == "value"


class TestDeleteDocument:
    """Tests for delete_document method."""
    
    def test_successful_deletion(self, index_manager, mock_vector_collection, bm25_store):
        """Test successful deletion from both stores."""
        # First, index a document
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1"],
            texts=["Hello world"],
            embeddings=[[0.1, 0.2]],
        )
        index_manager.index_document(request)
        
        # Now delete it
        result = index_manager.delete_document("doc123", "user456")
        
        assert result.success is True
        assert result.document_id == "doc123"
        assert result.vector_deleted is True
        assert result.bm25_deleted is True
        assert result.error is None
        
        # Verify stores are empty
        assert len(mock_vector_collection.documents) == 0
        assert not bm25_store.exists("doc123")
    
    def test_delete_nonexistent_document(self, index_manager):
        """Test deleting a document that doesn't exist."""
        result = index_manager.delete_document("nonexistent", "user456")
        
        # Should still succeed (idempotent operation)
        assert result.success is True
        assert result.bm25_deleted is False  # Nothing to delete
    
    def test_vector_delete_failure_continues(self, bm25_store, temp_bm25_dir):
        """Test that BM25 deletion continues even if vector deletion fails."""
        failing_collection = MockVectorCollection(fail_on_delete=True)
        manager = IndexManager(
            vector_collection=failing_collection,
            bm25_store=bm25_store,
        )
        
        # First, manually create a BM25 index
        from app.agent.retrieval import BM25Service, ChunkData
        service = BM25Service()
        service.build_index([ChunkData(chunk_id="c1", text="test")])
        bm25_store.save("doc123", service)
        
        result = manager.delete_document("doc123", "user456")
        
        # Should partially succeed
        assert result.success is True  # BM25 deletion succeeded
        assert result.vector_deleted is False
        assert result.bm25_deleted is True
        assert "Vector store deletion failed" in result.error


class TestCheckConsistency:
    """Tests for check_consistency method."""
    
    def test_consistency_check(self, index_manager, bm25_store):
        """Test consistency check for a document."""
        # Index a document
        request = IndexDocumentRequest(
            document_id="doc123",
            user_id="user456",
            chunk_ids=["chunk1"],
            texts=["Hello world"],
            embeddings=[[0.1, 0.2]],
        )
        index_manager.index_document(request)
        
        result = index_manager.check_consistency("doc123")
        
        assert result["bm25_exists"] is True
    
    def test_consistency_check_missing(self, index_manager):
        """Test consistency check for a missing document."""
        result = index_manager.check_consistency("nonexistent")
        
        assert result["bm25_exists"] is False
