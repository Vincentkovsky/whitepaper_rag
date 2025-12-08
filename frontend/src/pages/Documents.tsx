/**
 * Documents Page - Document management with upload, URL submit, and list
 * Requirements: 2.5
 */

import { useState, useEffect, useCallback } from 'react';
import { DocumentList, DocumentUpload, UrlSubmit } from '../components';
import { useDocumentStore } from '../stores/documentStore';
import { useUIStore } from '../stores/uiStore';
import { useAuthStore } from '../stores/authStore';
import { apiClient } from '../services/apiClient';
import type { Document } from '../types';

/**
 * Delete Confirmation Dialog Component
 */
interface DeleteDialogProps {
  document: Document | null;
  isOpen: boolean;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteDialog({ document, isOpen, isDeleting, onConfirm, onCancel }: DeleteDialogProps) {
  if (!isOpen || !document) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div
        className="bg-[var(--bg-secondary)] rounded-2xl shadow-2xl max-w-md w-full p-6 border border-[var(--border-color)] transform transition-all scale-100"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col items-center text-center sm:items-start sm:text-left">
          {/* Icon */}
          <div className="mx-auto sm:mx-0 w-12 h-12 rounded-full bg-error-100 dark:bg-error-900/30 flex items-center justify-center mb-4 shrink-0">
            <svg
              className="w-6 h-6 text-error-600 dark:text-error-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          {/* Content */}
          <div className="w-full">
            <h2
              id="delete-dialog-title"
              className="text-xl font-semibold text-[var(--text-primary)] mb-2"
            >
              Delete Document
            </h2>

            <p className="text-sm text-[var(--text-secondary)] mb-6 leading-relaxed">
              Are you sure you want to delete <span className="font-semibold text-[var(--text-primary)] break-all">{document.title || document.source_value || 'this document'}</span>?
              This action cannot be undone and will remove all associated data.
            </p>

            {/* Actions */}
            <div className="flex flex-col-reverse sm:flex-row gap-3 sm:justify-end w-full">
              <button
                onClick={onCancel}
                disabled={isDeleting}
                className="px-4 py-2.5 rounded-lg border border-[var(--border-color)] text-[var(--text-primary)] font-medium hover:bg-[var(--bg-tertiary)] transition-colors duration-200 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-gray-200 dark:focus:ring-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={isDeleting}
                className="px-4 py-2.5 rounded-lg bg-error-600 hover:bg-error-700 text-white font-medium transition-colors duration-200 disabled:opacity-50 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-error-500 focus:ring-offset-2 dark:focus:ring-offset-gray-900 shadow-sm"
              >
                {isDeleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Document</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Documents() {
  const [activeTab, setActiveTab] = useState<'upload' | 'url'>('upload');
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { documents, setDocuments, deleteDocument, setLoading } = useDocumentStore();
  const { showToast } = useUIStore();
  const { accessToken } = useAuthStore();

  /**
   * Fetch documents on mount (only after auth token is available)
   */
  useEffect(() => {
    // Wait until accessToken is available (store hydration complete)
    if (!accessToken) {
      return;
    }

    const fetchDocuments = async () => {
      setLoading(true);
      try {
        const response = await apiClient.get<Document[]>('/documents');
        setDocuments(response);
      } catch {
        showToast('error', 'Failed to load documents');
      } finally {
        setLoading(false);
      }
    };

    fetchDocuments();
  }, [accessToken, setDocuments, setLoading, showToast]);

  /**
   * Handle document delete request
   */
  const handleDeleteRequest = useCallback((document: Document) => {
    setDocumentToDelete(document);
  }, []);

  /**
   * Handle delete confirmation
   */
  const handleDeleteConfirm = useCallback(async () => {
    if (!documentToDelete) return;

    setIsDeleting(true);
    try {
      await apiClient.delete(`/documents/${documentToDelete.id}`);
      deleteDocument(documentToDelete.id);
      showToast('success', `${documentToDelete.title || documentToDelete.source_value} deleted successfully`);
      setDocumentToDelete(null);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete document';
      showToast('error', errorMessage);
    } finally {
      setIsDeleting(false);
    }
  }, [documentToDelete, deleteDocument, showToast]);

  /**
   * Handle delete cancel
   */
  const handleDeleteCancel = useCallback(() => {
    if (!isDeleting) {
      setDocumentToDelete(null);
    }
  }, [isDeleting]);

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-2">
            Documents
          </h1>
          <p className="text-[var(--text-secondary)]">
            Upload and manage your documents for AI-powered analysis
          </p>
        </div>

        {/* Upload Section */}
        <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] p-6 mb-8">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
            Add Document
          </h2>

          {/* Tab Switcher */}
          <div className="flex gap-1 p-1 bg-[var(--bg-tertiary)] rounded-lg mb-4 w-fit">
            <button
              onClick={() => setActiveTab('upload')}
              className={`
                px-4 py-2 rounded-md text-sm font-medium transition-all duration-200
                ${activeTab === 'upload'
                  ? 'bg-[var(--bg-secondary)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }
              `}
            >
              Upload File
            </button>
            <button
              onClick={() => setActiveTab('url')}
              className={`
                px-4 py-2 rounded-md text-sm font-medium transition-all duration-200
                ${activeTab === 'url'
                  ? 'bg-[var(--bg-secondary)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }
              `}
            >
              From URL
            </button>
          </div>

          {/* Upload Content */}
          {activeTab === 'upload' ? (
            <DocumentUpload />
          ) : (
            <UrlSubmit />
          )}
        </div>

        {/* Document List Section */}
        <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Your Documents
            </h2>
            <span className="text-sm text-[var(--text-muted)]">
              {documents.length} {documents.length === 1 ? 'document' : 'documents'}
            </span>
          </div>

          <DocumentList
            onDocumentDelete={handleDeleteRequest}
          />
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        document={documentToDelete}
        isOpen={!!documentToDelete}
        isDeleting={isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />
    </div>
  );
}

export default Documents;
