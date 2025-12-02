/**
 * Message Bubble Component
 * Displays chat messages with support for markdown, citations, thought process, and feedback
 * Requirements: 3.9
 */

import React, { useState } from 'react';
import type { ChatMessage, Citation } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ThoughtProcess } from './ThoughtProcess';

export interface MessageBubbleProps {
  /** The chat message to display */
  message: ChatMessage;
  /** Callback when a citation is clicked */
  onCitationClick?: (citation: Citation) => void;
  /** Callback when feedback is given */
  onFeedback?: (messageId: string, type: 'up' | 'down') => void;
  /** Whether the agent is currently generating this message */
  isStreaming?: boolean;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Thumbs Up Icon
 */
const ThumbsUpIcon: React.FC<{ filled?: boolean }> = ({ filled }) => (
  <svg 
    className="w-4 h-4" 
    fill={filled ? 'currentColor' : 'none'} 
    stroke="currentColor" 
    viewBox="0 0 24 24"
  >
    <path 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      strokeWidth={2} 
      d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" 
    />
  </svg>
);

/**
 * Thumbs Down Icon
 */
const ThumbsDownIcon: React.FC<{ filled?: boolean }> = ({ filled }) => (
  <svg 
    className="w-4 h-4" 
    fill={filled ? 'currentColor' : 'none'} 
    stroke="currentColor" 
    viewBox="0 0 24 24"
  >
    <path 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      strokeWidth={2} 
      d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" 
    />
  </svg>
);

/**
 * User Avatar
 */
const UserAvatar: React.FC = () => (
  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
    <svg className="w-5 h-5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  </div>
);

/**
 * Assistant Avatar
 */
const AssistantAvatar: React.FC = () => (
  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
    <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  </div>
);

/**
 * Feedback Buttons Component
 */
interface FeedbackButtonsProps {
  messageId: string;
  currentFeedback?: 'up' | 'down' | null;
  onFeedback?: (messageId: string, type: 'up' | 'down') => void;
}

const FeedbackButtons: React.FC<FeedbackButtonsProps> = ({
  messageId,
  currentFeedback,
  onFeedback,
}) => {
  const [hoveredButton, setHoveredButton] = useState<'up' | 'down' | null>(null);

  const handleFeedback = (type: 'up' | 'down') => {
    if (onFeedback) {
      onFeedback(messageId, type);
    }
  };

  return (
    <div 
      className="flex items-center gap-1 mt-2"
      data-testid="feedback-buttons"
    >
      <button
        type="button"
        onClick={() => handleFeedback('up')}
        onMouseEnter={() => setHoveredButton('up')}
        onMouseLeave={() => setHoveredButton(null)}
        className={`
          p-1.5 rounded transition-colors
          ${currentFeedback === 'up' 
            ? 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30' 
            : 'text-gray-400 hover:text-green-600 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20'
          }
        `}
        aria-label="Thumbs up"
        aria-pressed={currentFeedback === 'up'}
        data-testid="feedback-thumbs-up"
      >
        <ThumbsUpIcon filled={currentFeedback === 'up' || hoveredButton === 'up'} />
      </button>
      
      <button
        type="button"
        onClick={() => handleFeedback('down')}
        onMouseEnter={() => setHoveredButton('down')}
        onMouseLeave={() => setHoveredButton(null)}
        className={`
          p-1.5 rounded transition-colors
          ${currentFeedback === 'down' 
            ? 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30' 
            : 'text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
          }
        `}
        aria-label="Thumbs down"
        aria-pressed={currentFeedback === 'down'}
        data-testid="feedback-thumbs-down"
      >
        <ThumbsDownIcon filled={currentFeedback === 'down' || hoveredButton === 'down'} />
      </button>
    </div>
  );
};

/**
 * Message Bubble - Displays a single chat message
 */
export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onCitationClick,
  onFeedback,
  isStreaming = false,
  className = '',
}) => {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // Create citation metadata map for the markdown renderer
  const citationMetadata = React.useMemo(() => {
    if (!message.citations) return undefined;
    
    const map = new Map<string, Partial<Citation>>();
    for (const citation of message.citations) {
      const key = `${citation.documentId}:${citation.chunkId}`;
      map.set(key, citation);
    }
    return map;
  }, [message.citations]);

  return (
    <div 
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} ${className}`}
      data-testid={`message-bubble-${message.role}`}
      data-message-id={message.id}
    >
      {/* Avatar */}
      {isUser ? <UserAvatar /> : <AssistantAvatar />}
      
      {/* Message Content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Thought Process (for assistant messages) */}
        {isAssistant && message.thoughtSteps && message.thoughtSteps.length > 0 && (
          <div className="mb-2">
            <ThoughtProcess 
              steps={message.thoughtSteps} 
              isThinking={isStreaming}
              defaultExpanded={isStreaming}
            />
          </div>
        )}
        
        {/* Message Bubble */}
        <div 
          className={`
            rounded-2xl px-4 py-3
            ${isUser 
              ? 'bg-blue-600 text-white rounded-br-md' 
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md'
            }
          `}
        >
          {isUser ? (
            // User messages are plain text
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            // Assistant messages support markdown and citations
            <MarkdownRenderer 
              content={message.content}
              onCitationClick={onCitationClick}
              citationMetadata={citationMetadata}
            />
          )}
          
          {/* Streaming indicator */}
          {isStreaming && isAssistant && (
            <span className="inline-block w-2 h-4 ml-1 bg-gray-400 dark:bg-gray-500 animate-pulse rounded-sm" />
          )}
        </div>
        
        {/* Timestamp */}
        <div className={`mt-1 text-xs text-gray-400 dark:text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
          {new Date(message.timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </div>
        
        {/* Feedback Buttons (for assistant messages only) */}
        {isAssistant && !isStreaming && (
          <FeedbackButtons
            messageId={message.id}
            currentFeedback={message.feedback}
            onFeedback={onFeedback}
          />
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
