/**
 * URL Submit Component - Submit a URL to process as a document
 * Requirements: 2.2
 */

import { useState, useCallback } from 'react';
import { useDocumentStore } from '../stores/documentStore';
import { useUIStore } from '../stores/uiStore';
import { apiClient } from '../services/apiClient';
import type { Document } from '../types';

interface UrlSubmitProps {
  onSubmitComplete?: (document: Document) => void;
  onSubmitError?: (error: string) => void;
}

/**
 * Validate URL format
 */
function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function UrlSubmit({ onSubmitComplete, onSubmitError }: UrlSubmitProps) {
  const [url, setUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addDocument } = useDocumentStore();
  const { showToast } = useUIStore();

  /**
   * Handle URL submission
   */
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedUrl = url.trim();

    // Validate URL
    if (!trimmedUrl) {
      setError('Please enter a URL');
      return;
    }

    if (!isValidUrl(trimmedUrl)) {
      setError('Please enter a valid URL (http:// or https://)');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const response = await apiClient.post<Document>('/documents/submit-url', {
        url: trimmedUrl,
      });

      // Add document to store
      addDocument(response);
      setUrl('');
      showToast('success', 'URL submitted successfully. Processing...');
      onSubmitComplete?.(response);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to submit URL';
      setError(errorMessage);
      showToast('error', errorMessage);
      onSubmitError?.(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  }, [url, addDocument, showToast, onSubmitComplete, onSubmitError]);

  /**
   * Handle input change
   */
  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
    if (error) {
      setError(null);
    }
  }, [error]);

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
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
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
              />
            </svg>
          </div>
          <input
            type="text"
            value={url}
            onChange={handleChange}
            placeholder="Enter URL to process (e.g., https://example.com/document.pdf)"
            disabled={isSubmitting}
            className={`
              w-full pl-10 pr-4 py-2.5 rounded-lg border transition-colors duration-200
              bg-[var(--bg-secondary)] text-[var(--text-primary)]
              placeholder:text-[var(--text-muted)]
              focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
              disabled:opacity-50 disabled:cursor-not-allowed
              ${error
                ? 'border-error-500 focus:ring-error-500'
                : 'border-[var(--border-color)] hover:border-[var(--border-hover)]'
              }
            `}
            aria-label="URL input"
            aria-invalid={!!error}
            aria-describedby={error ? 'url-error' : undefined}
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !url.trim()}
          className={`
            px-4 py-2.5 rounded-lg font-medium transition-all duration-200
            flex items-center gap-2
            ${isSubmitting || !url.trim()
              ? 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] cursor-not-allowed'
              : 'bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700'
            }
          `}
        >
          {isSubmitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Submitting...</span>
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              <span>Add URL</span>
            </>
          )}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <p
          id="url-error"
          className="text-sm text-error-500 flex items-center gap-1.5"
          role="alert"
        >
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          {error}
        </p>
      )}

      {/* Help Text */}
      <p className="text-xs text-[var(--text-muted)]">
        Supported: PDF files, web pages, and documents accessible via URL
      </p>
    </form>
  );
}

export default UrlSubmit;
