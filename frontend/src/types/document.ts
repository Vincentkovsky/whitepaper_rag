/**
 * Document-related type definitions
 * Requirements: 7.1
 */

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed';

export interface Document {
  id: string;
  name: string;
  status: DocumentStatus;
  errorMessage?: string;
  createdAt: string;
  pageCount?: number;
}
