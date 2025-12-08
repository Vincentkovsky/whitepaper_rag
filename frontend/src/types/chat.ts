/**
 * Chat-related type definitions
 * Requirements: 7.1
 */

export interface ThoughtStep {
  thought: string;
  action: string;
  actionInput: unknown;
  observation: string;
}

export interface Citation {
  index: number;
  documentId: string;
  chunkId: string;
  page?: number;
  text: string;
  textSnippet: string;
  highlightCoords?: number[][];
  sourceType: 'pdf' | 'web';
  url?: string;
  title?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  thoughtSteps?: ThoughtStep[];
  feedback?: 'up' | 'down' | null;
  timestamp: string;
}

export interface Conversation {
  id: string;
  title: string;
  documentIds: string[];
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

export type AgentStatus =
  | 'idle'
  | 'thinking'
  | 'searching_docs'
  | 'searching_web'
  | 'analyzing'
  | 'generating';
