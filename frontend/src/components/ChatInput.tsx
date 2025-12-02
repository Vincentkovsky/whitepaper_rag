/**
 * Chat Input Component
 * Text input with send button and stop generation button
 * Requirements: 3.1, 3.8
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';

export interface ChatInputProps {
  /** Callback when a message is submitted */
  onSubmit: (message: string) => void;
  /** Callback when stop generation is clicked */
  onStop?: () => void;
  /** Whether the agent is currently generating */
  isGenerating?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Whether the input is disabled */
  disabled?: boolean;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Send Icon
 */
const SendIcon: React.FC<{ className?: string }> = ({ className = 'w-5 h-5' }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
    />
  </svg>
);

/**
 * Stop Icon
 */
const StopIcon: React.FC<{ className?: string }> = ({ className = 'w-5 h-5' }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

/**
 * Chat Input - Main input component for sending messages
 */
export const ChatInput: React.FC<ChatInputProps> = ({
  onSubmit,
  onStop,
  isGenerating = false,
  placeholder = 'Ask a question about your documents...',
  disabled = false,
  className = '',
}) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, []);

  useEffect(() => {
    adjustTextareaHeight();
  }, [message, adjustTextareaHeight]);

  const handleSubmit = useCallback(() => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled || isGenerating) return;

    onSubmit(trimmedMessage);
    setMessage('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [message, disabled, isGenerating, onSubmit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const canSubmit = message.trim().length > 0 && !disabled && !isGenerating;

  return (
    <div
      className={`bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 ${className}`}
      data-testid="chat-input"
    >
      {/* Input Row */}
      <div className="flex items-end gap-3 p-4">
        {/* Text Input */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isGenerating}
            rows={1}
            className={`
              w-full px-4 py-3 rounded-xl border resize-none
              bg-gray-50 dark:bg-gray-800
              border-gray-200 dark:border-gray-700
              text-gray-900 dark:text-gray-100
              placeholder-gray-500 dark:placeholder-gray-400
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors
            `}
            aria-label="Message input"
            data-testid="chat-input-textarea"
          />
        </div>

        {/* Action Button */}
        {isGenerating ? (
          <button
            type="button"
            onClick={onStop}
            className="flex-shrink-0 p-3 rounded-xl bg-red-500 hover:bg-red-600 text-white transition-colors"
            aria-label="Stop generating"
            data-testid="chat-input-stop"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`
              flex-shrink-0 p-3 rounded-xl transition-colors
              ${canSubmit
                ? 'bg-blue-500 hover:bg-blue-600 text-white'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
              }
            `}
            aria-label="Send message"
            data-testid="chat-input-send"
          >
            <SendIcon />
          </button>
        )}
      </div>

      {/* Hint Text */}
      <div className="px-4 pb-3 text-xs text-gray-500 dark:text-gray-400">
        Press <kbd className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 font-mono">Enter</kbd> to send,{' '}
        <kbd className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 font-mono">Shift+Enter</kbd> for new line
      </div>
    </div>
  );
};

export default ChatInput;
