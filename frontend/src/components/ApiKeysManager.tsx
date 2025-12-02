/**
 * API Keys Manager - List, create, and delete API keys
 * Requirements: 4.4
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/apiClient';
import { useUIStore } from '../stores/uiStore';

/**
 * API Key data model
 */
export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  createdAt: string;
  lastUsedAt?: string;
}

/**
 * Create API Key response
 */
interface CreateApiKeyResponse {
  id: string;
  name: string;
  key: string;
  prefix: string;
  createdAt: string;
}

/**
 * Skeleton loader for API keys list
 */
function ApiKeysSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="p-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)]"
        >
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <div className="h-4 bg-[var(--bg-secondary)] rounded w-32" />
              <div className="h-3 bg-[var(--bg-secondary)] rounded w-24" />
            </div>
            <div className="h-8 w-16 bg-[var(--bg-secondary)] rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state component
 */
function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="text-center py-8">
      <div className="mx-auto w-12 h-12 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center mb-4">
        <svg
          className="w-6 h-6 text-[var(--text-muted)]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
          />
        </svg>
      </div>
      <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">
        No API Keys
      </h3>
      <p className="text-sm text-[var(--text-muted)] mb-4">
        Create an API key to access the API programmatically
      </p>
      <button
        onClick={onCreateClick}
        className="px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors duration-200"
      >
        Create API Key
      </button>
    </div>
  );
}

/**
 * New key display modal
 */
interface NewKeyModalProps {
  keyData: CreateApiKeyResponse | null;
  onClose: () => void;
}

function NewKeyModal({ keyData, onClose }: NewKeyModalProps) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useUIStore();

  const handleCopy = useCallback(async () => {
    if (!keyData) return;
    try {
      await navigator.clipboard.writeText(keyData.key);
      setCopied(true);
      showToast('success', 'API key copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast('error', 'Failed to copy to clipboard');
    }
  }, [keyData, showToast]);

  if (!keyData) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-key-modal-title"
    >
      <div
        className="bg-[var(--bg-secondary)] rounded-xl shadow-xl max-w-md w-full p-6 border border-[var(--border-color)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Success Icon */}
        <div className="mx-auto w-12 h-12 rounded-full bg-success-100 dark:bg-success-900/30 flex items-center justify-center mb-4">
          <svg
            className="w-6 h-6 text-success-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        {/* Title */}
        <h2
          id="new-key-modal-title"
          className="text-lg font-semibold text-[var(--text-primary)] text-center mb-2"
        >
          API Key Created
        </h2>

        {/* Warning */}
        <p className="text-sm text-warning-500 text-center mb-4">
          Make sure to copy your API key now. You won't be able to see it again!
        </p>

        {/* Key Display */}
        <div className="mb-4">
          <label className="block text-xs text-[var(--text-muted)] mb-1">
            {keyData.name}
          </label>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] text-sm font-mono text-[var(--text-primary)] break-all">
              {keyData.key}
            </code>
            <button
              onClick={handleCopy}
              className="p-2 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-tertiary)] transition-colors duration-200"
              title="Copy to clipboard"
            >
              {copied ? (
                <svg
                  className="w-5 h-5 text-success-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5 text-[var(--text-secondary)]"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="w-full px-4 py-2.5 rounded-lg bg-primary-500 text-white font-medium hover:bg-primary-600 transition-colors duration-200"
        >
          Done
        </button>
      </div>
    </div>
  );
}

/**
 * Create key modal
 */
interface CreateKeyModalProps {
  isOpen: boolean;
  isCreating: boolean;
  onClose: () => void;
  onCreate: (name: string) => void;
}

function CreateKeyModal({ isOpen, isCreating, onClose, onCreate }: CreateKeyModalProps) {
  const [name, setName] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) {
      onCreate(name.trim());
    }
  };

  const handleClose = () => {
    if (!isCreating) {
      setName('');
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-key-modal-title"
    >
      <div
        className="bg-[var(--bg-secondary)] rounded-xl shadow-xl max-w-md w-full p-6 border border-[var(--border-color)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <h2
          id="create-key-modal-title"
          className="text-lg font-semibold text-[var(--text-primary)] mb-4"
        >
          Create API Key
        </h2>

        <form onSubmit={handleSubmit}>
          {/* Name Input */}
          <div className="mb-4">
            <label
              htmlFor="key-name"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Key Name
            </label>
            <input
              id="key-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Production API Key"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              disabled={isCreating}
              autoFocus
            />
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Give your key a descriptive name to identify it later
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={isCreating}
              className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-color)] text-[var(--text-primary)] font-medium hover:bg-[var(--bg-tertiary)] transition-colors duration-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating || !name.trim()}
              className="flex-1 px-4 py-2.5 rounded-lg bg-primary-500 text-white font-medium hover:bg-primary-600 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isCreating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Creating...</span>
                </>
              ) : (
                <span>Create Key</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Delete confirmation modal
 */
interface DeleteKeyModalProps {
  apiKey: ApiKey | null;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function DeleteKeyModal({ apiKey, isDeleting, onClose, onConfirm }: DeleteKeyModalProps) {
  if (!apiKey) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-key-modal-title"
    >
      <div
        className="bg-[var(--bg-secondary)] rounded-xl shadow-xl max-w-md w-full p-6 border border-[var(--border-color)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Warning Icon */}
        <div className="mx-auto w-12 h-12 rounded-full bg-error-100 dark:bg-error-900/30 flex items-center justify-center mb-4">
          <svg
            className="w-6 h-6 text-error-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </div>

        {/* Title */}
        <h2
          id="delete-key-modal-title"
          className="text-lg font-semibold text-[var(--text-primary)] text-center mb-2"
        >
          Delete API Key
        </h2>

        {/* Message */}
        <p className="text-sm text-[var(--text-secondary)] text-center mb-6">
          Are you sure you want to delete{' '}
          <span className="font-medium text-[var(--text-primary)]">{apiKey.name}</span>?
          Any applications using this key will stop working.
        </p>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-color)] text-[var(--text-primary)] font-medium hover:bg-[var(--bg-tertiary)] transition-colors duration-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="flex-1 px-4 py-2.5 rounded-lg bg-error-500 text-white font-medium hover:bg-error-600 transition-colors duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isDeleting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Deleting...</span>
              </>
            ) : (
              <span>Delete Key</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
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

export function ApiKeysManager() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newKeyData, setNewKeyData] = useState<CreateApiKeyResponse | null>(null);
  const [keyToDelete, setKeyToDelete] = useState<ApiKey | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const { showToast } = useUIStore();

  /**
   * Fetch API keys on mount
   */
  useEffect(() => {
    const fetchApiKeys = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get<ApiKey[]>('/api-keys');
        setApiKeys(response);
      } catch {
        showToast('error', 'Failed to load API keys');
      } finally {
        setIsLoading(false);
      }
    };

    fetchApiKeys();
  }, [showToast]);

  /**
   * Create new API key
   */
  const handleCreateKey = useCallback(
    async (name: string) => {
      setIsCreating(true);
      try {
        const response = await apiClient.post<CreateApiKeyResponse>('/api-keys', { name });
        setNewKeyData(response);
        setApiKeys((prev) => [
          ...prev,
          {
            id: response.id,
            name: response.name,
            prefix: response.prefix,
            createdAt: response.createdAt,
          },
        ]);
        setIsCreateModalOpen(false);
        showToast('success', 'API key created successfully');
      } catch {
        showToast('error', 'Failed to create API key');
      } finally {
        setIsCreating(false);
      }
    },
    [showToast]
  );

  /**
   * Delete API key
   */
  const handleDeleteKey = useCallback(async () => {
    if (!keyToDelete) return;

    setIsDeleting(true);
    try {
      await apiClient.delete(`/api-keys/${keyToDelete.id}`);
      setApiKeys((prev) => prev.filter((key) => key.id !== keyToDelete.id));
      setKeyToDelete(null);
      showToast('success', 'API key deleted successfully');
    } catch {
      showToast('error', 'Failed to delete API key');
    } finally {
      setIsDeleting(false);
    }
  }, [keyToDelete, showToast]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">API Keys</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Manage your API keys for programmatic access
          </p>
        </div>
        {apiKeys.length > 0 && (
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors duration-200 flex items-center gap-2"
          >
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
            Create Key
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <ApiKeysSkeleton />
      ) : apiKeys.length === 0 ? (
        <EmptyState onCreateClick={() => setIsCreateModalOpen(true)} />
      ) : (
        <div className="space-y-3" role="list">
          {apiKeys.map((key) => (
            <div
              key={key.id}
              className="p-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)]"
              role="listitem"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-[var(--text-primary)]">{key.name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <code className="text-xs text-[var(--text-muted)] font-mono">
                      {key.prefix}...
                    </code>
                    <span className="text-xs text-[var(--text-muted)]">
                      Created {formatDate(key.createdAt)}
                    </span>
                    {key.lastUsedAt && (
                      <span className="text-xs text-[var(--text-muted)]">
                        Last used {formatDate(key.lastUsedAt)}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setKeyToDelete(key)}
                  className="p-2 rounded-lg text-[var(--text-muted)] hover:text-error-500 hover:bg-error-50 dark:hover:bg-error-900/20 transition-colors duration-200"
                  title="Delete API key"
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
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
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateKeyModal
        isOpen={isCreateModalOpen}
        isCreating={isCreating}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={handleCreateKey}
      />

      <NewKeyModal keyData={newKeyData} onClose={() => setNewKeyData(null)} />

      <DeleteKeyModal
        apiKey={keyToDelete}
        isDeleting={isDeleting}
        onClose={() => !isDeleting && setKeyToDelete(null)}
        onConfirm={handleDeleteKey}
      />
    </div>
  );
}

export default ApiKeysManager;
