/**
 * Storage Service - LocalStorage persistence for conversations and settings
 * Requirements: 6.4, 7.2, 7.3
 */

import type { Conversation } from '../types';

const STORAGE_KEYS = {
  CONVERSATIONS: 'agentic_rag_conversations',
  THEME: 'agentic_rag_theme',
} as const;

type Theme = 'light' | 'dark';

/**
 * Validate conversation object structure
 */
const isValidConversation = (obj: unknown): obj is Conversation => {
  if (!obj || typeof obj !== 'object') return false;
  
  const conv = obj as Record<string, unknown>;
  
  return (
    typeof conv.id === 'string' &&
    typeof conv.title === 'string' &&
    Array.isArray(conv.documentIds) &&
    Array.isArray(conv.messages) &&
    typeof conv.createdAt === 'string' &&
    typeof conv.updatedAt === 'string'
  );
};

/**
 * Validate conversations array
 */
const validateConversations = (data: unknown): Conversation[] => {
  if (!Array.isArray(data)) {
    return [];
  }
  
  return data.filter(isValidConversation);
};

/**
 * Pretty print JSON for debugging (development mode only)
 */
export const prettyPrintState = (state: unknown): string => {
  return JSON.stringify(state, null, 2);
};


/**
 * Storage Service API
 */
export const storageService = {
  /**
   * Save conversations to localStorage
   * Requirements: 6.4, 7.2
   */
  saveConversations: (conversations: Conversation[]): void => {
    try {
      const json = JSON.stringify(conversations);
      localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, json);
      
      if (import.meta.env.DEV) {
        console.debug('[StorageService] Saved conversations:', prettyPrintState(conversations));
      }
    } catch (error) {
      console.error('[StorageService] Failed to save conversations:', error);
    }
  },

  /**
   * Load conversations from localStorage
   * Requirements: 6.4, 7.3
   */
  loadConversations: (): Conversation[] => {
    try {
      const json = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      
      if (!json) {
        return [];
      }
      
      const parsed = JSON.parse(json);
      const validated = validateConversations(parsed);
      
      if (import.meta.env.DEV) {
        console.debug('[StorageService] Loaded conversations:', prettyPrintState(validated));
      }
      
      return validated;
    } catch (error) {
      console.error('[StorageService] Failed to load conversations:', error);
      return [];
    }
  },

  /**
   * Save theme preference
   * Requirements: 5.4
   */
  saveTheme: (theme: Theme): void => {
    try {
      localStorage.setItem(STORAGE_KEYS.THEME, theme);
    } catch (error) {
      console.error('[StorageService] Failed to save theme:', error);
    }
  },

  /**
   * Load theme preference
   * Requirements: 5.4
   */
  loadTheme: (): Theme => {
    try {
      const theme = localStorage.getItem(STORAGE_KEYS.THEME);
      
      if (theme === 'light' || theme === 'dark') {
        return theme;
      }
      
      // Default to system preference
      if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      
      return 'light';
    } catch {
      return 'light';
    }
  },

  /**
   * Clear all stored data
   */
  clearAll: (): void => {
    try {
      localStorage.removeItem(STORAGE_KEYS.CONVERSATIONS);
      localStorage.removeItem(STORAGE_KEYS.THEME);
    } catch (error) {
      console.error('[StorageService] Failed to clear storage:', error);
    }
  },

  /**
   * Get storage keys (for testing/debugging)
   */
  getStorageKeys: () => STORAGE_KEYS,
};

export default storageService;
