/**
 * Document List Component - Displays documents with name, status, and upload date
 * Requirements: 2.3, 2.4
 */

import { useEffect, useRef, useCallback } from 'react';
import { useDocumentStore } from '../stores/documentStore';
import { apiClient } from '../services/apiClient';
import type { Document, DocumentStatus } from '../types';

interface DocumentListProps {
  onDocumentSelect?: (document: Document) => void;
  onDocumentDelete?: (document: Document) => void;
}

// Status polling interval in milliseconds
const POLLING_INTERVAL = 3000;

/**
 * Get status badge styling based on document status
 */
function getStatusBadgeClass(status: DocumentStatus): string {
  const baseClass = 'px-2 py-1 text-xs font-medium rounded-full';
  switch (status) {
    case 'completed':
      return `${baseClass} bg-success-100 text-success-700 dark:bg-success-900/30 dark:text-success-400`;
    case 'parsing':
      return `${baseClass} bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400`;
    case 'uploading':
      return `${baseClass} bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-400`;
    case 'failed':
      return `${baseClass} bg-error-100 text-error-700 dark:bg-error-900/30 dark:text-error-400`;
    default:
      return `${baseClass} bg-gray-100 text-gray-700`;
  }
}

/**
 * Get human-readable status text
 */
function getStatusText(status: DocumentStatus): string {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'parsing':
      return 'Parsing';
    case 'uploading':
      return 'Uploading';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function DocumentList({ onDocumentSelect, onDocumentDelete }: DocumentListProps) {
  const { documents, updateDocument, isLoading, selectedDocumentId, setSelectedDocument } = useDocumentStore();
  const pollingRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  /**
   * Poll document status for processing documents
   */
  const pollDocumentStatus = useCallback(async (documentId: string) => {
    try {
      if (!documentId) {
        return;
      }
      const response = await apiClient.get<{ status: DocumentStatus; error_message?: string }>(
        `/documents/${documentId}/status`
      );

      updateDocument(documentId, {
        status: response.status,
        error_message: response.error_message,
      });

      // Stop polling if document is no longer processing
      if (response.status !== 'parsing' && response.status !== 'uploading') {
        const timeoutId = pollingRef.current.get(documentId);
        if (timeoutId) {
          clearInterval(timeoutId);
          pollingRef.current.delete(documentId);
        }
      }
    } catch (error) {
      console.error(`Failed to poll status for document ${documentId}:`, error);
    }
  }, [updateDocument]);

  /**
   * Start polling for processing documents
   */
  /**
   * Manage polling lifecycle
   * Reconciles active polls with document status
   */
  useEffect(() => {
    const processingDocIds = new Set(
      documents
        .filter(doc => doc.status === 'parsing' || doc.status === 'uploading')
        .map(doc => doc.id)
    );

    // 1. Stop polling for documents that are no longer processing
    for (const [docId, intervalId] of pollingRef.current.entries()) {
      if (!processingDocIds.has(docId)) {
        clearInterval(intervalId);
        pollingRef.current.delete(docId);
      }
    }

    // 2. Start polling for new processing documents
    for (const docId of processingDocIds) {
      if (!pollingRef.current.has(docId)) {
        const intervalId = setInterval(() => {
          pollDocumentStatus(docId);
        }, POLLING_INTERVAL);
        pollingRef.current.set(docId, intervalId);

        // Also poll immediately
        pollDocumentStatus(docId);
      }
    }
  }, [documents, pollDocumentStatus]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      for (const intervalId of pollingRef.current.values()) {
        clearInterval(intervalId);
      }
      pollingRef.current.clear();
    };
  }, []);

  const handleDocumentClick = (document: Document) => {
    setSelectedDocument(document.id);
    onDocumentSelect?.(document);
  };

  const handleDeleteClick = (e: React.MouseEvent, document: Document) => {
    e.stopPropagation();
    onDocumentDelete?.(document);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div
            key={i}
            className="animate-pulse bg-[var(--bg-secondary)] rounded-lg p-4 border border-[var(--border-color)]"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="h-4 bg-[var(--bg-tertiary)] rounded w-3/4 mb-2" />
                <div className="h-3 bg-[var(--bg-tertiary)] rounded w-1/4" />
              </div>
              <div className="h-6 w-16 bg-[var(--bg-tertiary)] rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-[var(--text-muted)]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-[var(--text-primary)]">
          No documents yet
        </h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Upload a PDF or submit a URL to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2" role="list" aria-label="Document list">
      {documents.map(document => (
        <div
          key={document.id}
          role="listitem"
          onClick={() => handleDocumentClick(document)}
          className={`
            group cursor-pointer rounded-lg p-4 border transition-all duration-200
            ${selectedDocumentId === document.id
              ? 'bg-primary-50 border-primary-300 dark:bg-primary-900/20 dark:border-primary-700'
              : 'bg-[var(--bg-secondary)] border-[var(--border-color)] hover:bg-[var(--bg-tertiary)] hover:border-[var(--border-hover)]'
            }
          `}
        >
          <div className="flex items-start justify-between gap-4">
            {/* Document Icon and Info */}
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="flex-shrink-0 mt-0.5">
                <svg
                  className="h-5 w-5 text-[var(--text-muted)]"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-[var(--text-primary)] truncate">
                  {document.title || document.source_value}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-[var(--text-muted)]">
                    {formatDate(document.created_at)}
                  </span>
                </div>
                {document.status === 'failed' && document.error_message && (
                  <p className="mt-1 text-xs text-error-500 truncate">
                    {document.error_message}
                  </p>
                )}
              </div>
            </div>

            {/* Status Badge and Actions */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={getStatusBadgeClass(document.status)}>
                {document.status === 'parsing' && (
                  <span className="inline-block w-2 h-2 mr-1.5 bg-current rounded-full animate-pulse" />
                )}
                {getStatusText(document.status)}
              </span>

              {/* Delete Button */}
              <button
                onClick={(e) => handleDeleteClick(e, document)}
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md text-[var(--text-muted)] hover:text-error-500 hover:bg-error-50 dark:hover:bg-error-900/20 transition-all duration-200"
                aria-label={`Delete ${document.title || document.source_value}`}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default DocumentList;
