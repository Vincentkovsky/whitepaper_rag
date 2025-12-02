/**
 * Document Upload Component - Drag and drop or click to upload PDF files
 * Requirements: 2.1
 */

import { useState, useRef, useCallback } from 'react';
import { useDocumentStore } from '../stores/documentStore';
import { useUIStore } from '../stores/uiStore';
import { apiClient } from '../services/apiClient';
import type { Document } from '../types';

interface DocumentUploadProps {
  onUploadComplete?: (document: Document) => void;
  onUploadError?: (error: string) => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED_FILE_TYPES = ['application/pdf'];

export function DocumentUpload({ onUploadComplete, onUploadError }: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const { addDocument, setUploadProgress, clearUploadProgress } = useDocumentStore();
  const { showToast } = useUIStore();

  /**
   * Validate file before upload
   */
  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
      return 'Only PDF files are supported';
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`;
    }
    return null;
  };

  /**
   * Handle file upload
   */
  const uploadFile = useCallback(async (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      showToast('error', validationError);
      onUploadError?.(validationError);
      return;
    }

    const fileId = `upload-${Date.now()}-${file.name}`;
    setIsUploading(true);
    setUploadProgress(fileId, 0);

    try {
      const response = await apiClient.upload<Document>(
        '/documents/upload',
        file,
        (progress) => {
          setUploadProgress(fileId, progress);
        }
      );

      // Add document to store
      addDocument(response);
      clearUploadProgress(fileId);
      showToast('success', `${file.name} uploaded successfully`);
      onUploadComplete?.(response);
    } catch (error) {
      clearUploadProgress(fileId);
      const errorMessage = error instanceof Error ? error.message : 'Upload failed';
      showToast('error', errorMessage);
      onUploadError?.(errorMessage);
    } finally {
      setIsUploading(false);
    }
  }, [addDocument, setUploadProgress, clearUploadProgress, showToast, onUploadComplete, onUploadError]);

  /**
   * Handle drag events
   */
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  }, [uploadFile]);

  /**
   * Handle click to upload
   */
  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handle file input change
   */
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
    // Reset input value to allow uploading the same file again
    e.target.value = '';
  }, [uploadFile]);

  // Get current upload progress
  const { uploadProgress } = useDocumentStore();
  const currentProgress = Array.from(uploadProgress.values())[0] || 0;

  return (
    <div
      className={`
        relative rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer
        ${isDragging
          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
          : 'border-[var(--border-color)] hover:border-primary-400 hover:bg-[var(--bg-tertiary)]'
        }
        ${isUploading ? 'pointer-events-none opacity-75' : ''}
      `}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
      aria-label="Upload PDF file"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileChange}
        className="hidden"
        aria-hidden="true"
      />

      <div className="flex flex-col items-center justify-center py-8 px-4">
        {isUploading ? (
          <>
            {/* Upload Progress */}
            <div className="w-12 h-12 mb-4 relative">
              <svg className="w-12 h-12 transform -rotate-90" viewBox="0 0 36 36">
                <circle
                  cx="18"
                  cy="18"
                  r="16"
                  fill="none"
                  className="stroke-[var(--bg-tertiary)]"
                  strokeWidth="3"
                />
                <circle
                  cx="18"
                  cy="18"
                  r="16"
                  fill="none"
                  className="stroke-primary-500"
                  strokeWidth="3"
                  strokeDasharray={`${currentProgress} 100`}
                  strokeLinecap="round"
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-[var(--text-primary)]">
                {currentProgress}%
              </span>
            </div>
            <p className="text-sm text-[var(--text-secondary)]">Uploading...</p>
          </>
        ) : (
          <>
            {/* Upload Icon */}
            <div className={`
              w-12 h-12 mb-4 rounded-full flex items-center justify-center
              ${isDragging
                ? 'bg-primary-100 dark:bg-primary-900/40'
                : 'bg-[var(--bg-tertiary)]'
              }
            `}>
              <svg
                className={`w-6 h-6 ${isDragging ? 'text-primary-500' : 'text-[var(--text-muted)]'}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>

            {/* Instructions */}
            <p className="text-sm font-medium text-[var(--text-primary)] mb-1">
              {isDragging ? 'Drop your file here' : 'Drag and drop your PDF'}
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              or <span className="text-primary-500 hover:text-primary-600">browse</span> to upload
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-2">
              PDF files up to 50MB
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default DocumentUpload;
