/**
 * Chat Store - Manages conversation and message state
 * Requirements: 6.1, 6.3
 */

import { create } from 'zustand';
import type { Conversation, ChatMessage, AgentStatus } from '../types';

interface ChatState {
  conversations: Conversation[];
  currentSessionId: string | null;
  agentStatus: AgentStatus;
}

interface ChatActions {
  // Conversation actions
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  setCurrentSession: (sessionId: string | null) => void;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;

  // Message actions
  addMessage: (conversationId: string, message: ChatMessage) => void;
  appendToMessage: (conversationId: string, messageId: string, content: string) => void;
  setFeedback: (conversationId: string, messageId: string, feedback: 'up' | 'down' | null) => void;

  // Status actions
  setAgentStatus: (status: AgentStatus) => void;
}

interface ChatStore extends ChatState, ChatActions {
  currentConversation: Conversation | null;
  messages: ChatMessage[];
}

export const useChatStore = create<ChatStore>((set, get) => ({
  // State
  conversations: [],
  currentSessionId: null,
  agentStatus: 'idle',

  // Computed
  get currentConversation() {
    const state = get();
    return state.conversations.find(c => c.id === state.currentSessionId) ?? null;
  },

  get messages() {
    const state = get();
    const conversation = state.conversations.find(c => c.id === state.currentSessionId);
    return conversation?.messages ?? [];
  },

  // Conversation actions
  setConversations: (conversations: Conversation[]) => {
    set({ conversations });
  },

  addConversation: (conversation: Conversation) => {
    set(state => ({
      conversations: [...state.conversations, conversation],
    }));
  },

  setCurrentSession: (sessionId: string | null) => {
    set({ currentSessionId: sessionId });
  },

  updateConversation: (id: string, updates: Partial<Conversation>) => {
    set(state => ({
      conversations: state.conversations.map(c =>
        c.id === id ? { ...c, ...updates, updatedAt: new Date().toISOString() } : c
      ),
    }));
  },

  deleteConversation: (id: string) => {
    set(state => ({
      conversations: state.conversations.filter(c => c.id !== id),
      currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
    }));
  },

  // Message actions
  addMessage: (conversationId: string, message: ChatMessage) => {
    set(state => ({
      conversations: state.conversations.map(c =>
        c.id === conversationId
          ? {
              ...c,
              messages: [...c.messages, message],
              updatedAt: new Date().toISOString(),
            }
          : c
      ),
    }));
  },

  appendToMessage: (conversationId: string, messageId: string, content: string) => {
    set(state => ({
      conversations: state.conversations.map(c =>
        c.id === conversationId
          ? {
              ...c,
              messages: c.messages.map(m =>
                m.id === messageId ? { ...m, content: m.content + content } : m
              ),
              updatedAt: new Date().toISOString(),
            }
          : c
      ),
    }));
  },

  setFeedback: (conversationId: string, messageId: string, feedback: 'up' | 'down' | null) => {
    set(state => ({
      conversations: state.conversations.map(c =>
        c.id === conversationId
          ? {
              ...c,
              messages: c.messages.map(m =>
                m.id === messageId ? { ...m, feedback } : m
              ),
            }
          : c
      ),
    }));
  },

  // Status actions
  setAgentStatus: (status: AgentStatus) => {
    set({ agentStatus: status });
  },
}));
