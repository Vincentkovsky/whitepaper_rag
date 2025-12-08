/**
 * Chat Workbench Page
 * Main chat interface
 * Requirements: 3.1, 3.2, 8.1, 8.7
 */

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChatInput,
  MessageBubble,
  StatusIndicator,
} from '../components';
import { useChatStore } from '../stores/chatStore';
import { useDocumentStore } from '../stores/documentStore';
import { useUIStore } from '../stores/uiStore';
import { useAuthStore } from '../stores/authStore';
import { SSEClient, type SSEClientOptions } from '../services/sseClient';
import { apiClient } from '../services/apiClient';
import { storageService } from '../services/storageService';
import type { Citation, ChatMessage, ThoughtStep, Conversation, Document } from '../types';

/**
 * Generate a unique ID
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a conversation title from the first message
 */
function generateTitle(message: string): string {
  const maxLength = 50;
  const cleaned = message.trim().replace(/\s+/g, ' ');
  if (cleaned.length <= maxLength) return cleaned;
  return cleaned.substring(0, maxLength).trim() + '...';
}

/**
 * Throttle function for batching UI updates
 */
function createThrottledUpdater<T>(
  callback: (value: T) => void,
  delay: number
): { update: (value: T) => void; flush: () => void } {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let pendingValue: T | null = null;

  const flush = () => {
    if (pendingValue !== null) {
      callback(pendingValue);
      pendingValue = null;
    }
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  const update = (value: T) => {
    pendingValue = value;
    if (!timeoutId) {
      timeoutId = setTimeout(() => {
        flush();
      }, delay);
    }
  };

  return { update, flush };
}

/**
 * Chat Area Icon
 */
const ChatAreaIcon: React.FC<{ className?: string }> = ({ className = 'w-5 h-5' }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
    />
  </svg>
);

export interface ChatWorkbenchProps {
  /** Session ID from URL params (optional) */
  sessionId?: string;
}

export function ChatWorkbench() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();

  // Stores
  const {
    conversations,
    currentSessionId,
    agentStatus,
    setConversations,
    addConversation,
    setCurrentSession,
    updateConversation,
    addMessage,
    setFeedback,
    setAgentStatus,
  } = useChatStore();

  const { setDocuments } = useDocumentStore();
  const { showToast } = useUIStore();
  const { accessToken } = useAuthStore();

  // Local state
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_pendingThoughtSteps, setPendingThoughtSteps] = useState<ThoughtStep[]>([]);

  // Refs
  const sseClientRef = useRef<SSEClient | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const contentAccumulatorRef = useRef<string>('');

  // Get current conversation
  const currentConversation = useMemo(() => {
    return conversations.find(c => c.id === currentSessionId) ?? null;
  }, [conversations, currentSessionId]);

  const messages = currentConversation?.messages ?? [];

  // Load conversations from storage on mount
  useEffect(() => {
    const savedConversations = storageService.loadConversations();
    if (savedConversations.length > 0) {
      setConversations(savedConversations);
    }
  }, [setConversations]);

  // Fetch documents after auth token is available
  useEffect(() => {
    if (!accessToken) return;

    const fetchDocuments = async () => {
      try {
        const docs = await apiClient.get<Document[]>('/documents');
        setDocuments(docs);
      } catch {
        // Silently fail - documents are optional
      }
    };
    fetchDocuments();
  }, [accessToken, setDocuments]);

  // Handle URL session ID
  useEffect(() => {
    if (urlSessionId && urlSessionId !== currentSessionId) {
      const exists = conversations.some(c => c.id === urlSessionId);
      if (exists) {
        setCurrentSession(urlSessionId);
      }
    }
  }, [urlSessionId, currentSessionId, conversations, setCurrentSession]);

  // Save conversations when they change
  useEffect(() => {
    if (conversations.length > 0) {
      storageService.saveConversations(conversations);
    }
  }, [conversations]);

  // Scroll to bottom when messages change
  const messagesLength = messages.length;
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messagesLength, streamingMessageId]);


  /**
   * Handle citation click - No-op now as EvidenceBoard is removed
   */
  const handleCitationClick = useCallback((citation: Citation) => {
    // Optional: Scroll to citation in message or show tooltip
    console.log('Citation clicked:', citation);
  }, []);

  /**
   * Handle feedback
   */
  const handleFeedback = useCallback(async (messageId: string, type: 'up' | 'down') => {
    if (!currentSessionId) return;

    setFeedback(currentSessionId, messageId, type);

    // Send feedback to backend
    try {
      await apiClient.post('/agent/feedback', {
        messageId,
        feedback: type,
        sessionId: currentSessionId,
      });
    } catch {
      // Silently fail - feedback is not critical
    }
  }, [currentSessionId, setFeedback]);

  /**
   * Stop generation
   */
  const handleStopGeneration = useCallback(() => {
    sseClientRef.current?.abort();
    setIsGenerating(false);
    setAgentStatus('idle');
    setStreamingMessageId(null);
  }, [setAgentStatus]);

  /**
   * Handle message submission with SSE streaming
   */
  const handleSubmit = useCallback(async (message: string) => {
    // Create conversation if none exists
    let conversationId = currentSessionId;
    if (!conversationId) {
      const newConversation: Conversation = {
        id: generateId(),
        title: generateTitle(message),
        documentIds: [], // No longer selecting documents explicitly
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      addConversation(newConversation);
      setCurrentSession(newConversation.id);
      conversationId = newConversation.id;
    } else {
      // Update title if this is the first message
      const conv = conversations.find(c => c.id === conversationId);
      if (conv && conv.messages.length === 0) {
        updateConversation(conversationId, { title: generateTitle(message) });
      }
    }

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    addMessage(conversationId, userMessage);

    // Create assistant message placeholder
    const assistantMessageId = generateId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      thoughtSteps: [],
      timestamp: new Date().toISOString(),
    };
    addMessage(conversationId, assistantMessage);

    // Reset state
    setIsGenerating(true);
    setStreamingMessageId(assistantMessageId);
    setAgentStatus('thinking');
    contentAccumulatorRef.current = '';
    setPendingThoughtSteps([]);

    // Create throttled content updater (50ms batching)
    const throttledContentUpdate = createThrottledUpdater<string>((content) => {
      if (conversationId) {
        // Update the message content directly - defer to avoid setState during render
        queueMicrotask(() => {
          useChatStore.setState(state => ({
            conversations: state.conversations.map(c =>
              c.id === conversationId
                ? {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMessageId ? { ...m, content } : m
                  ),
                }
                : c
            ),
          }));
        });
      }
    }, 50);

    // SSE event handlers
    const sseOptions: SSEClientOptions = {
      onThinking: (content) => {
        setAgentStatus('thinking');
        // Add to thought steps
        setPendingThoughtSteps(prev => {
          const newSteps = [...prev, {
            thought: content,
            action: '',
            actionInput: null,
            observation: '',
          }];
          // Update message with thought steps - defer to avoid setState during render
          if (conversationId) {
            queueMicrotask(() => {
              useChatStore.setState(state => ({
                conversations: state.conversations.map(c =>
                  c.id === conversationId
                    ? {
                      ...c,
                      messages: c.messages.map(m =>
                        m.id === assistantMessageId ? { ...m, thoughtSteps: newSteps } : m
                      ),
                    }
                    : c
                ),
              }));
            });
          }
          return newSteps;
        });
      },

      onToolCall: (tool, input) => {
        // Update status based on tool
        if (tool === 'web_search' || tool === 'search_web') {
          setAgentStatus('searching_web');
        } else if (tool === 'search_documents' || tool === 'retrieve') {
          setAgentStatus('searching_docs');
        } else {
          setAgentStatus('analyzing');
        }

        // Update thought steps with action
        setPendingThoughtSteps(prev => {
          const newSteps = [...prev];
          if (newSteps.length > 0) {
            newSteps[newSteps.length - 1] = {
              ...newSteps[newSteps.length - 1],
              action: tool,
              actionInput: input,
            };
          } else {
            newSteps.push({
              thought: '',
              action: tool,
              actionInput: input,
              observation: '',
            });
          }
          return newSteps;
        });
      },

      onToolResult: (_tool, result) => {
        // Update thought steps with observation
        setPendingThoughtSteps(prev => {
          const newSteps = [...prev];
          if (newSteps.length > 0) {
            newSteps[newSteps.length - 1] = {
              ...newSteps[newSteps.length - 1],
              observation: typeof result === 'string' ? result : JSON.stringify(result),
            };
          }
          return newSteps;
        });
      },

      onAnswer: (content, sources) => {
        setAgentStatus('generating');
        contentAccumulatorRef.current += content;
        throttledContentUpdate.update(contentAccumulatorRef.current);

        // Update citations if provided
        if (sources && sources.length > 0 && conversationId) {
          queueMicrotask(() => {
            useChatStore.setState(state => ({
              conversations: state.conversations.map(c =>
                c.id === conversationId
                  ? {
                    ...c,
                    messages: c.messages.map(m =>
                      m.id === assistantMessageId ? { ...m, citations: sources } : m
                    ),
                  }
                  : c
              ),
            }));
          });
        }
      },

      onError: (errorMessage) => {
        showToast('error', errorMessage);
        setIsGenerating(false);
        setAgentStatus('idle');
        setStreamingMessageId(null);
      },

      onDone: () => {
        // Flush any pending content
        throttledContentUpdate.flush();
        setIsGenerating(false);
        setAgentStatus('idle');
        setStreamingMessageId(null);
      },

      onConnectionError: (error) => {
        showToast('error', `Connection error: ${error.message}`);
        setIsGenerating(false);
        setAgentStatus('idle');
        setStreamingMessageId(null);
      },
    };

    // Start SSE connection
    const sseClient = new SSEClient();
    sseClientRef.current = sseClient;

    try {
      await sseClient.connect(
        `${apiClient.getBaseUrl()}/agent/chat/stream`,
        {
          question: message,
          model: 'mini',
        },
        sseOptions
      );
    } catch (error) {
      showToast('error', error instanceof Error ? error.message : 'Failed to connect');
      setIsGenerating(false);
      setAgentStatus('idle');
      setStreamingMessageId(null);
    }
  }, [
    currentSessionId,
    conversations,
    addConversation,
    setCurrentSession,
    updateConversation,
    addMessage,
    setAgentStatus,
    showToast,
  ]);


  return (
    <div className="h-full flex bg-gray-50 dark:bg-gray-950" data-testid="chat-workbench">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Chat Area */}
        <div
          className="flex-1 flex flex-col min-w-0 overflow-hidden"
          data-testid="chat-area"
        >
          {/* Chat Header */}
          <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
            <div className="flex items-center gap-3 overflow-hidden">
              <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">
                {currentConversation?.title || 'New Conversation'}
              </h1>
            </div>

            <div className="flex items-center gap-2">
              {/* New Chat Button */}
              <button
                onClick={() => {
                  const newConversation: Conversation = {
                    id: generateId(),
                    title: 'New conversation',
                    documentIds: [],
                    messages: [],
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString(),
                  };
                  addConversation(newConversation);
                  setCurrentSession(newConversation.id);
                  navigate(`/chat/${newConversation.id}`);
                }}
                className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                title="New Chat"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>

              {/* Status Indicator */}
              {agentStatus !== 'idle' && (
                <StatusIndicator status={agentStatus} />
              )}
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
                  <ChatAreaIcon className="w-8 h-8 text-blue-500" />
                </div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Start a conversation
                </h2>
                <p className="text-gray-500 dark:text-gray-400 max-w-md">
                  Refracting complexity into clarity.
                </p>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    onCitationClick={handleCitationClick}
                    onFeedback={handleFeedback}
                    isStreaming={msg.id === streamingMessageId}
                  />
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Chat Input - fixed at bottom via flex layout */}
          <div className="flex-shrink-0 z-10">
            <ChatInput
              onSubmit={handleSubmit}
              onStop={handleStopGeneration}
              isGenerating={isGenerating}
              disabled={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatWorkbench;
