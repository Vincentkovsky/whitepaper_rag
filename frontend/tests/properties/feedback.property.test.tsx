/**
 * Property-Based Tests for Feedback Buttons
 * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
 * **Validates: Requirements 3.9**
 *
 * Property: For any agent response message, the rendered output should include
 * both thumbs up and thumbs down buttons.
 */

import { describe, it, expect, vi } from 'vitest';
import * as fc from 'fast-check';
import { render, fireEvent } from '@testing-library/react';
import { MessageBubble } from '../../src/components/MessageBubble';
import type { ChatMessage, Citation, ThoughtStep } from '../../src/types';

// Generator for valid UUIDs
const uuidArbitrary = fc.uuid();

// Generator for timestamps (using integer to avoid invalid date issues)
const timestampArbitrary = fc.integer({ min: 1577836800000, max: 1893456000000 }) // 2020-01-01 to 2030-01-01
  .map(ms => new Date(ms).toISOString());

// Generator for message content
const contentArbitrary = fc.string({ minLength: 1, maxLength: 500 });

// Generator for citation
const citationArbitrary: fc.Arbitrary<Citation> = fc.record({
  index: fc.nat({ max: 10 }),
  documentId: uuidArbitrary,
  chunkId: uuidArbitrary,
  page: fc.option(fc.nat({ max: 100 }), { nil: undefined }),
  text: fc.string({ minLength: 1, maxLength: 200 }),
  textSnippet: fc.string({ minLength: 1, maxLength: 100 }),
  highlightCoords: fc.option(
    fc.array(fc.array(fc.double({ min: 0, max: 1000, noNaN: true }), { minLength: 4, maxLength: 4 })),
    { nil: undefined }
  ),
  sourceType: fc.constantFrom('pdf', 'web') as fc.Arbitrary<'pdf' | 'web'>,
  url: fc.option(fc.webUrl(), { nil: undefined }),
});

// Generator for thought step
const thoughtStepArbitrary: fc.Arbitrary<ThoughtStep> = fc.record({
  thought: fc.string({ minLength: 1, maxLength: 200 }),
  action: fc.string({ minLength: 1, maxLength: 50 }),
  actionInput: fc.jsonValue(),
  observation: fc.string({ minLength: 1, maxLength: 200 }),
});

// Generator for assistant message (which should have feedback buttons)
const assistantMessageArbitrary: fc.Arbitrary<ChatMessage> = fc.record({
  id: uuidArbitrary,
  role: fc.constant('assistant') as fc.Arbitrary<'assistant'>,
  content: contentArbitrary,
  citations: fc.option(fc.array(citationArbitrary, { minLength: 0, maxLength: 3 }), { nil: undefined }),
  thoughtSteps: fc.option(fc.array(thoughtStepArbitrary, { minLength: 0, maxLength: 3 }), { nil: undefined }),
  feedback: fc.constantFrom(null, 'up', 'down') as fc.Arbitrary<'up' | 'down' | null>,
  timestamp: timestampArbitrary,
});

// Generator for user message (which should NOT have feedback buttons)
const userMessageArbitrary: fc.Arbitrary<ChatMessage> = fc.record({
  id: uuidArbitrary,
  role: fc.constant('user') as fc.Arbitrary<'user'>,
  content: contentArbitrary,
  citations: fc.constant(undefined),
  thoughtSteps: fc.constant(undefined),
  feedback: fc.constant(null) as fc.Arbitrary<null>,
  timestamp: timestampArbitrary,
});

describe('Feedback Buttons Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * For any assistant message, the rendered output should include both
   * thumbs up and thumbs down buttons.
   */
  it('assistant messages have both thumbs up and thumbs down buttons', () => {
    fc.assert(
      fc.property(assistantMessageArbitrary, (message) => {
        const { container } = render(
          <MessageBubble message={message} />
        );
        
        // Should have feedback buttons container
        const feedbackButtons = container.querySelector('[data-testid="feedback-buttons"]');
        expect(feedbackButtons).not.toBeNull();
        
        // Should have thumbs up button
        const thumbsUp = container.querySelector('[data-testid="feedback-thumbs-up"]');
        expect(thumbsUp).not.toBeNull();
        
        // Should have thumbs down button
        const thumbsDown = container.querySelector('[data-testid="feedback-thumbs-down"]');
        expect(thumbsDown).not.toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * User messages should NOT have feedback buttons.
   */
  it('user messages do not have feedback buttons', () => {
    fc.assert(
      fc.property(userMessageArbitrary, (message) => {
        const { container } = render(
          <MessageBubble message={message} />
        );
        
        // Should NOT have feedback buttons
        const feedbackButtons = container.querySelector('[data-testid="feedback-buttons"]');
        expect(feedbackButtons).toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * Clicking thumbs up should call onFeedback with 'up'.
   */
  it('clicking thumbs up calls onFeedback with correct type', () => {
    fc.assert(
      fc.property(assistantMessageArbitrary, (message) => {
        const onFeedback = vi.fn();
        const { container } = render(
          <MessageBubble message={message} onFeedback={onFeedback} />
        );
        
        const thumbsUp = container.querySelector('[data-testid="feedback-thumbs-up"]');
        expect(thumbsUp).not.toBeNull();
        
        fireEvent.click(thumbsUp!);
        
        expect(onFeedback).toHaveBeenCalledWith(message.id, 'up');
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * Clicking thumbs down should call onFeedback with 'down'.
   */
  it('clicking thumbs down calls onFeedback with correct type', () => {
    fc.assert(
      fc.property(assistantMessageArbitrary, (message) => {
        const onFeedback = vi.fn();
        const { container } = render(
          <MessageBubble message={message} onFeedback={onFeedback} />
        );
        
        const thumbsDown = container.querySelector('[data-testid="feedback-thumbs-down"]');
        expect(thumbsDown).not.toBeNull();
        
        fireEvent.click(thumbsDown!);
        
        expect(onFeedback).toHaveBeenCalledWith(message.id, 'down');
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * Feedback buttons should have proper accessibility attributes.
   */
  it('feedback buttons have proper accessibility attributes', () => {
    fc.assert(
      fc.property(assistantMessageArbitrary, (message) => {
        const { container } = render(
          <MessageBubble message={message} />
        );
        
        const thumbsUp = container.querySelector('[data-testid="feedback-thumbs-up"]');
        const thumbsDown = container.querySelector('[data-testid="feedback-thumbs-down"]');
        
        // Should have aria-label
        expect(thumbsUp?.getAttribute('aria-label')).toBeTruthy();
        expect(thumbsDown?.getAttribute('aria-label')).toBeTruthy();
        
        // Should have aria-pressed
        expect(thumbsUp?.hasAttribute('aria-pressed')).toBe(true);
        expect(thumbsDown?.hasAttribute('aria-pressed')).toBe(true);
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * When feedback is 'up', thumbs up should be visually indicated as pressed.
   */
  it('thumbs up shows pressed state when feedback is up', () => {
    fc.assert(
      fc.property(
        assistantMessageArbitrary.map(m => ({ ...m, feedback: 'up' as const })),
        (message) => {
          const { container } = render(
            <MessageBubble message={message} />
          );
          
          const thumbsUp = container.querySelector('[data-testid="feedback-thumbs-up"]');
          expect(thumbsUp?.getAttribute('aria-pressed')).toBe('true');
        }
      ),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * When feedback is 'down', thumbs down should be visually indicated as pressed.
   */
  it('thumbs down shows pressed state when feedback is down', () => {
    fc.assert(
      fc.property(
        assistantMessageArbitrary.map(m => ({ ...m, feedback: 'down' as const })),
        (message) => {
          const { container } = render(
            <MessageBubble message={message} />
          );
          
          const thumbsDown = container.querySelector('[data-testid="feedback-thumbs-down"]');
          expect(thumbsDown?.getAttribute('aria-pressed')).toBe('true');
        }
      ),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * Streaming messages should NOT show feedback buttons.
   */
  it('streaming messages do not show feedback buttons', () => {
    fc.assert(
      fc.property(assistantMessageArbitrary, (message) => {
        const { container } = render(
          <MessageBubble message={message} isStreaming={true} />
        );
        
        // Should NOT have feedback buttons while streaming
        const feedbackButtons = container.querySelector('[data-testid="feedback-buttons"]');
        expect(feedbackButtons).toBeNull();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 7: Agent response feedback buttons**
   * **Validates: Requirements 3.9**
   *
   * Message bubble should render with correct role data attribute.
   */
  it('message bubble has correct role data attribute', () => {
    const anyMessageArbitrary = fc.oneof(assistantMessageArbitrary, userMessageArbitrary);
    
    fc.assert(
      fc.property(anyMessageArbitrary, (message) => {
        const { container } = render(
          <MessageBubble message={message} />
        );
        
        const bubble = container.querySelector(`[data-testid="message-bubble-${message.role}"]`);
        expect(bubble).not.toBeNull();
        expect(bubble?.getAttribute('data-message-id')).toBe(message.id);
      }),
      { numRuns: 50 }
    );
  });
});
