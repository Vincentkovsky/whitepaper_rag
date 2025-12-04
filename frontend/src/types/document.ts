/**
 * Document-related type definitions
 * Requirements: 7.1
 */

export type DocumentStatus = 'uploading' | 'parsing' | 'completed' | 'failed';

export interface Document {
  id: string;
  user_id: string;
  source_type: 'pdf' | 'url' | 'text';
  source_value: string;
  title?: string;
  status: DocumentStatus;
  error_message?: string;
  created_at: string;
  updated_at: string;
}
