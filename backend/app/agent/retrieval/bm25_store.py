"""
BM25 Index Persistence Store.

This module provides save/load functionality for BM25 indexes using Pickle serialization.
Storage path: backend/app/storage/bm25_indexes/{document_id}.pkl

Requirements: 6.2 - THE Agentic_RAG_System SHALL support keyword-based search using BM25 algorithm.
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from .bm25_service import BM25Service, ChunkData


# Default storage directory for BM25 indexes
DEFAULT_STORAGE_PATH = Path(__file__).parent.parent.parent / "storage" / "bm25_indexes"


@dataclass
class BM25IndexData:
    """
    Serializable data structure for BM25 index persistence.
    
    Contains all data needed to reconstruct a BM25Service instance.
    """
    document_id: str
    chunks: List[ChunkData]
    tokenized_corpus: List[List[str]]


class BM25IndexStore:
    """
    Persistence store for BM25 indexes.
    
    Handles saving and loading BM25 indexes to/from disk using Pickle serialization.
    Each document's index is stored in a separate file named {document_id}.pkl.
    
    Example:
        >>> store = BM25IndexStore()
        >>> service = BM25Service()
        >>> service.build_index([ChunkData(chunk_id="1", text="Hello world")])
        >>> store.save("doc123", service)
        >>> loaded_service = store.load("doc123")
        >>> loaded_service.is_indexed
        True
    """
    
    def __init__(self, storage_path: Optional[Path] = None) -> None:
        """
        Initialize the BM25 index store.
        
        Args:
            storage_path: Directory path for storing index files.
                         Defaults to backend/app/storage/bm25_indexes/
        """
        self._storage_path = storage_path or DEFAULT_STORAGE_PATH
        self._ensure_storage_dir()
    
    @property
    def storage_path(self) -> Path:
        """Get the storage directory path."""
        return self._storage_path
    
    def _ensure_storage_dir(self) -> None:
        """Create the storage directory if it doesn't exist."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
    
    def _get_index_path(self, document_id: str) -> Path:
        """
        Get the file path for a document's index.
        
        Args:
            document_id: The document identifier
            
        Returns:
            Path to the index file
        """
        return self._storage_path / f"{document_id}.pkl"
    
    def save(self, document_id: str, service: BM25Service) -> None:
        """
        Save a BM25 index to disk.
        
        Serializes the index data (chunks and tokenized corpus) to a Pickle file.
        The BM25Okapi index is rebuilt on load from the tokenized corpus.
        
        Args:
            document_id: Unique identifier for the document
            service: BM25Service instance with a built index
            
        Raises:
            ValueError: If the service has no built index
            IOError: If the file cannot be written
        """
        if not service.is_indexed:
            raise ValueError("Cannot save: BM25Service has no built index")
        
        index_data = BM25IndexData(
            document_id=document_id,
            chunks=service.get_chunks(),
            tokenized_corpus=service.get_tokenized_corpus(),
        )
        
        index_path = self._get_index_path(document_id)
        
        with open(index_path, "wb") as f:
            pickle.dump(index_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    def load(self, document_id: str) -> Optional[BM25Service]:
        """
        Load a BM25 index from disk.
        
        Deserializes the index data and rebuilds the BM25Service instance.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            BM25Service instance with the loaded index, or None if not found
            
        Raises:
            IOError: If the file exists but cannot be read
            pickle.UnpicklingError: If the file is corrupted
        """
        index_path = self._get_index_path(document_id)
        
        if not index_path.exists():
            return None
        
        with open(index_path, "rb") as f:
            index_data: BM25IndexData = pickle.load(f)
        
        # Rebuild the BM25Service from the stored data
        service = BM25Service()
        service._chunks = index_data.chunks
        service._tokenized_corpus = index_data.tokenized_corpus
        service._index = BM25Okapi(index_data.tokenized_corpus)
        
        return service
    
    def exists(self, document_id: str) -> bool:
        """
        Check if an index exists for a document.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            True if the index file exists, False otherwise
        """
        return self._get_index_path(document_id).exists()
    
    def delete(self, document_id: str) -> bool:
        """
        Delete a document's index from disk.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            True if the index was deleted, False if it didn't exist
        """
        index_path = self._get_index_path(document_id)
        
        if index_path.exists():
            index_path.unlink()
            return True
        
        return False
    
    def list_indexes(self) -> List[str]:
        """
        List all stored document IDs.
        
        Returns:
            List of document IDs that have stored indexes
        """
        return [
            p.stem for p in self._storage_path.glob("*.pkl")
        ]
