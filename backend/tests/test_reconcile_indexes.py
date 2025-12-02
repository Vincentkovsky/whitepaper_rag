"""
Tests for the index reconciliation script.

Tests the ReconciliationReport and IndexReconciler classes.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
import tempfile

from scripts.reconcile_indexes import (
    ReconciliationReport,
    IndexReconciler,
)
from app.agent.retrieval.bm25_store import BM25IndexStore
from app.agent.retrieval.bm25_service import BM25Service, ChunkData


class TestReconciliationReport:
    """Tests for ReconciliationReport dataclass."""
    
    def test_consistent_documents(self):
        """Test consistent_documents property returns intersection."""
        report = ReconciliationReport(
            chromadb_documents={"doc1", "doc2", "doc3"},
            bm25_documents={"doc2", "doc3", "doc4"},
        )
        assert report.consistent_documents == {"doc2", "doc3"}
    
    def test_total_inconsistencies(self):
        """Test total_inconsistencies counts orphaned entries."""
        report = ReconciliationReport(
            orphaned_in_chromadb={"doc1"},
            orphaned_in_bm25={"doc4", "doc5"},
        )
        assert report.total_inconsistencies == 3
    
    def test_is_consistent_true(self):
        """Test is_consistent returns True when no orphans."""
        report = ReconciliationReport(
            chromadb_documents={"doc1", "doc2"},
            bm25_documents={"doc1", "doc2"},
            orphaned_in_chromadb=set(),
            orphaned_in_bm25=set(),
        )
        assert report.is_consistent is True
    
    def test_is_consistent_false(self):
        """Test is_consistent returns False when orphans exist."""
        report = ReconciliationReport(
            orphaned_in_chromadb={"doc1"},
            orphaned_in_bm25=set(),
        )
        assert report.is_consistent is False
    
    def test_summary_consistent(self):
        """Test summary output for consistent state."""
        report = ReconciliationReport(
            chromadb_documents={"doc1"},
            bm25_documents={"doc1"},
        )
        summary = report.summary()
        assert "All indexes are consistent" in summary
    
    def test_summary_inconsistent(self):
        """Test summary output for inconsistent state."""
        report = ReconciliationReport(
            chromadb_documents={"doc1", "doc2"},
            bm25_documents={"doc2", "doc3"},
            orphaned_in_chromadb={"doc1"},
            orphaned_in_bm25={"doc3"},
        )
        summary = report.summary()
        assert "2 inconsistencies" in summary
        assert "doc1" in summary
        assert "doc3" in summary


class TestIndexReconciler:
    """Tests for IndexReconciler class."""
    
    def test_get_bm25_document_ids(self):
        """Test getting document IDs from BM25 store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BM25IndexStore(storage_path=Path(tmpdir))
            
            # Create some test indexes
            for doc_id in ["doc1", "doc2"]:
                service = BM25Service()
                service.build_index([ChunkData(chunk_id="c1", text="test")])
                store.save(doc_id, service)
            
            # Create reconciler with mock chroma
            mock_collection = MagicMock()
            reconciler = IndexReconciler(
                chroma_collection=mock_collection,
                bm25_store=store,
            )
            
            doc_ids = reconciler.get_bm25_document_ids()
            assert doc_ids == {"doc1", "doc2"}
    
    def test_get_chromadb_document_ids(self):
        """Test getting document IDs from ChromaDB."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "metadatas": [
                {"document_id": "doc1", "user_id": "user1"},
                {"document_id": "doc1", "user_id": "user1"},  # Duplicate chunk
                {"document_id": "doc2", "user_id": "user1"},
            ]
        }
        
        reconciler = IndexReconciler(
            chroma_collection=mock_collection,
            bm25_store=MagicMock(),
        )
        
        doc_ids = reconciler.get_chromadb_document_ids()
        assert doc_ids == {"doc1", "doc2"}
    
    def test_reconcile_consistent(self):
        """Test reconciliation when stores are consistent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BM25IndexStore(storage_path=Path(tmpdir))
            
            # Create BM25 indexes
            for doc_id in ["doc1", "doc2"]:
                service = BM25Service()
                service.build_index([ChunkData(chunk_id="c1", text="test")])
                store.save(doc_id, service)
            
            # Mock ChromaDB with same documents
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "metadatas": [
                    {"document_id": "doc1"},
                    {"document_id": "doc2"},
                ]
            }
            
            reconciler = IndexReconciler(
                chroma_collection=mock_collection,
                bm25_store=store,
            )
            
            report = reconciler.reconcile()
            assert report.is_consistent
            assert report.consistent_documents == {"doc1", "doc2"}
    
    def test_reconcile_inconsistent(self):
        """Test reconciliation when stores are inconsistent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BM25IndexStore(storage_path=Path(tmpdir))
            
            # Create BM25 index for doc2 only
            service = BM25Service()
            service.build_index([ChunkData(chunk_id="c1", text="test")])
            store.save("doc2", service)
            
            # Mock ChromaDB with doc1 only
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "metadatas": [{"document_id": "doc1"}]
            }
            
            reconciler = IndexReconciler(
                chroma_collection=mock_collection,
                bm25_store=store,
            )
            
            report = reconciler.reconcile()
            assert not report.is_consistent
            assert report.orphaned_in_chromadb == {"doc1"}
            assert report.orphaned_in_bm25 == {"doc2"}
    
    def test_reconcile_with_auto_fix(self):
        """Test auto-fix removes orphaned BM25 indexes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BM25IndexStore(storage_path=Path(tmpdir))
            
            # Create orphaned BM25 index
            service = BM25Service()
            service.build_index([ChunkData(chunk_id="c1", text="test")])
            store.save("orphaned_doc", service)
            
            # Mock empty ChromaDB
            mock_collection = MagicMock()
            mock_collection.get.return_value = {"metadatas": []}
            
            reconciler = IndexReconciler(
                chroma_collection=mock_collection,
                bm25_store=store,
            )
            
            # Verify index exists before fix
            assert store.exists("orphaned_doc")
            
            report = reconciler.reconcile(auto_fix=True)
            
            # Verify index was removed
            assert not store.exists("orphaned_doc")
            assert "orphaned_doc" in report.fixed_bm25
