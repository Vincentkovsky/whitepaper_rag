#!/usr/bin/env python3
"""
Index Reconciliation Script.

Compares ChromaDB document IDs with BM25 index files to identify and
optionally fix inconsistencies between the two stores.

Requirements: 6.2 - THE Agentic_RAG_System SHALL support keyword-based search using BM25 algorithm.

Usage:
    python -m backend.scripts.reconcile_indexes [--fix] [--verbose]
    
Options:
    --fix       Automatically fix inconsistencies by removing orphaned entries
    --verbose   Show detailed information about each document
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

import chromadb
from chromadb.config import Settings as ChromaSettings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.core.config import get_settings
from backend.app.agent.retrieval.bm25_store import BM25IndexStore


@dataclass
class ReconciliationReport:
    """Report of index reconciliation results."""
    
    # Documents found in each store
    chromadb_documents: Set[str] = field(default_factory=set)
    bm25_documents: Set[str] = field(default_factory=set)
    
    # Inconsistencies
    orphaned_in_chromadb: Set[str] = field(default_factory=set)  # In ChromaDB but not BM25
    orphaned_in_bm25: Set[str] = field(default_factory=set)      # In BM25 but not ChromaDB
    
    # Fix results
    fixed_chromadb: List[str] = field(default_factory=list)
    fixed_bm25: List[str] = field(default_factory=list)
    fix_errors: List[str] = field(default_factory=list)
    
    @property
    def consistent_documents(self) -> Set[str]:
        """Documents that exist in both stores."""
        return self.chromadb_documents & self.bm25_documents
    
    @property
    def total_inconsistencies(self) -> int:
        """Total number of inconsistent documents."""
        return len(self.orphaned_in_chromadb) + len(self.orphaned_in_bm25)
    
    @property
    def is_consistent(self) -> bool:
        """Check if both stores are fully consistent."""
        return self.total_inconsistencies == 0
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 60,
            "INDEX RECONCILIATION REPORT",
            "=" * 60,
            f"ChromaDB documents:     {len(self.chromadb_documents)}",
            f"BM25 documents:         {len(self.bm25_documents)}",
            f"Consistent documents:   {len(self.consistent_documents)}",
            "-" * 60,
        ]
        
        if self.is_consistent:
            lines.append("✓ All indexes are consistent!")
        else:
            lines.append(f"✗ Found {self.total_inconsistencies} inconsistencies:")
            
            if self.orphaned_in_chromadb:
                lines.append(f"\n  In ChromaDB only ({len(self.orphaned_in_chromadb)}):")
                for doc_id in sorted(self.orphaned_in_chromadb):
                    lines.append(f"    - {doc_id}")
            
            if self.orphaned_in_bm25:
                lines.append(f"\n  In BM25 only ({len(self.orphaned_in_bm25)}):")
                for doc_id in sorted(self.orphaned_in_bm25):
                    lines.append(f"    - {doc_id}")
        
        if self.fixed_chromadb or self.fixed_bm25:
            lines.append("-" * 60)
            lines.append("FIXES APPLIED:")
            if self.fixed_chromadb:
                lines.append(f"  Removed from ChromaDB: {len(self.fixed_chromadb)}")
            if self.fixed_bm25:
                lines.append(f"  Removed from BM25: {len(self.fixed_bm25)}")
        
        if self.fix_errors:
            lines.append("-" * 60)
            lines.append("FIX ERRORS:")
            for error in self.fix_errors:
                lines.append(f"  - {error}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class IndexReconciler:
    """
    Reconciles ChromaDB and BM25 indexes.
    
    Compares document IDs across both stores and identifies inconsistencies.
    Can optionally auto-fix by removing orphaned entries.
    """
    
    def __init__(
        self,
        chroma_collection: Optional[chromadb.Collection] = None,
        bm25_store: Optional[BM25IndexStore] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the reconciler.
        
        Args:
            chroma_collection: ChromaDB collection to check. If None, uses default.
            bm25_store: BM25 index store. If None, uses default.
            logger: Logger instance. If None, creates one.
        """
        self._logger = logger or logging.getLogger("reconcile_indexes")
        
        if chroma_collection is None:
            chroma_collection = self._get_default_chroma_collection()
        self._chroma_collection = chroma_collection
        
        self._bm25_store = bm25_store or BM25IndexStore()
    
    def _get_default_chroma_collection(self) -> chromadb.Collection:
        """Get the default ChromaDB collection from settings."""
        settings = get_settings()
        
        if settings.chroma_server_host:
            chroma = chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
                ssl=settings.chroma_server_ssl,
                headers={"Authorization": f"Bearer {settings.chroma_server_api_key}"}
                if settings.chroma_server_api_key else None,
            )
        elif settings.chroma_persist_directory:
            persist_dir = Path(settings.chroma_persist_directory)
            chroma_settings = ChromaSettings(
                persist_directory=str(persist_dir),
                anonymized_telemetry=False,
            )
            chroma = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=chroma_settings,
            )
        else:
            chroma_settings = ChromaSettings(anonymized_telemetry=False)
            chroma = chromadb.Client(settings=chroma_settings)
        
        collection_name = settings.chroma_collection or "documents"
        return chroma.get_or_create_collection(collection_name)
    
    def get_chromadb_document_ids(self) -> Set[str]:
        """
        Get all unique document IDs from ChromaDB.
        
        Extracts document_id from chunk metadata.
        
        Returns:
            Set of document IDs found in ChromaDB
        """
        document_ids: Set[str] = set()
        
        try:
            # Get all items from the collection
            results = self._chroma_collection.get(include=["metadatas"])
            
            if results and results.get("metadatas"):
                for metadata in results["metadatas"]:
                    if metadata and "document_id" in metadata:
                        document_ids.add(metadata["document_id"])
            
            self._logger.debug(
                f"Found {len(document_ids)} unique documents in ChromaDB"
            )
        except Exception as e:
            self._logger.error(f"Failed to query ChromaDB: {e}")
            raise
        
        return document_ids
    
    def get_bm25_document_ids(self) -> Set[str]:
        """
        Get all document IDs with BM25 indexes.
        
        Returns:
            Set of document IDs with BM25 index files
        """
        document_ids = set(self._bm25_store.list_indexes())
        self._logger.debug(f"Found {len(document_ids)} BM25 indexes")
        return document_ids
    
    def reconcile(self, auto_fix: bool = False) -> ReconciliationReport:
        """
        Compare indexes and identify inconsistencies.
        
        Args:
            auto_fix: If True, automatically remove orphaned entries
            
        Returns:
            ReconciliationReport with findings and fix results
        """
        report = ReconciliationReport()
        
        # Gather document IDs from both stores
        self._logger.info("Scanning ChromaDB for document IDs...")
        report.chromadb_documents = self.get_chromadb_document_ids()
        
        self._logger.info("Scanning BM25 indexes...")
        report.bm25_documents = self.get_bm25_document_ids()
        
        # Find inconsistencies
        report.orphaned_in_chromadb = report.chromadb_documents - report.bm25_documents
        report.orphaned_in_bm25 = report.bm25_documents - report.chromadb_documents
        
        if report.orphaned_in_chromadb:
            self._logger.warning(
                f"Found {len(report.orphaned_in_chromadb)} documents in ChromaDB without BM25 index"
            )
        
        if report.orphaned_in_bm25:
            self._logger.warning(
                f"Found {len(report.orphaned_in_bm25)} BM25 indexes without ChromaDB entries"
            )
        
        # Auto-fix if requested
        if auto_fix and not report.is_consistent:
            self._apply_fixes(report)
        
        return report
    
    def _apply_fixes(self, report: ReconciliationReport) -> None:
        """
        Apply fixes to remove orphaned entries.
        
        For orphaned ChromaDB entries: These are documents that were indexed
        in ChromaDB but BM25 indexing failed. We leave them as-is since
        vector search still works.
        
        For orphaned BM25 entries: These are stale indexes where the ChromaDB
        entries were deleted. We remove the BM25 index files.
        
        Args:
            report: ReconciliationReport to update with fix results
        """
        self._logger.info("Applying fixes...")
        
        # Remove orphaned BM25 indexes (ChromaDB is source of truth)
        for doc_id in report.orphaned_in_bm25:
            try:
                deleted = self._bm25_store.delete(doc_id)
                if deleted:
                    report.fixed_bm25.append(doc_id)
                    self._logger.info(f"Removed orphaned BM25 index: {doc_id}")
            except Exception as e:
                error_msg = f"Failed to delete BM25 index {doc_id}: {e}"
                report.fix_errors.append(error_msg)
                self._logger.error(error_msg)
        
        # Note: We don't delete orphaned ChromaDB entries because:
        # 1. ChromaDB is the primary store for RAG functionality
        # 2. Missing BM25 index just means keyword search won't work
        # 3. The system falls back to vector-only search gracefully
        if report.orphaned_in_chromadb:
            self._logger.info(
                f"Skipping {len(report.orphaned_in_chromadb)} ChromaDB-only documents "
                "(vector search still functional, BM25 can be rebuilt)"
            )


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Main entry point for the reconciliation script.
    
    Returns:
        Exit code: 0 if consistent, 1 if inconsistencies found, 2 on error
    """
    parser = argparse.ArgumentParser(
        description="Reconcile ChromaDB and BM25 indexes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix inconsistencies by removing orphaned entries",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information",
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger("reconcile_indexes")
    
    try:
        reconciler = IndexReconciler(logger=logger)
        report = reconciler.reconcile(auto_fix=args.fix)
        
        print(report.summary())
        
        if report.fix_errors:
            return 2
        elif report.is_consistent or (args.fix and report.total_inconsistencies == len(report.fixed_bm25)):
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
