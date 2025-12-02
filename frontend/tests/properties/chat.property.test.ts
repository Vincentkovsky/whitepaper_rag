/**
 * Property-Based Tests for Chat Store
 * **Feature: frontend-redesign, Property 12: Message append preserves history**
 * **Validates: Requirements 6.3**
 *
 * Property: For any conversation with existing messages, appending a new message
 * should preserve all previous messages and add the new one.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { useChatStore } from '../../src/stores/chatStore';
import type { Conversation, ChatMessage, Citation, ThoughtStep } from '../../src/types';

// Generator for ThoughtStep
const thoughtStepArbitrary: fc.Arbitrary<ThoughtStep> = fc.record({
  thought: fc.string({ minLength: 1, maxLength: 200 }),
  action: fc.string({ minLength: 1, maxLength: 50 }),
  actionInput: fc.jsonValue(),
  observation: fc.string({ minLength: 1, maxLength: 200 }),
});

// Generator for Citation
const citationArbitrary: fc.Arbitrary<Citation> = fc.record({
  index: fc.nat({ max: 100 }),
  documentId: fc.uuid(),
  chunkId: fc.uuid(),
  page: fc.option(fc.nat({ max: 1000 }), { nil: undefined }),
  text: fc.string({ minLength: 1, maxLength: 500 }),
  textSnippet: fc.string({ minLength: 1, maxLength: 200 }),
  highlightCoords: fc.option(fc.array(fc.array(fc.float(), { minLength: 4, maxLength: 4 })), { nil: undefined }),
  sourceType: fc.constantFrom('pdf', 'web') as fc.Arbitrary<'pdf' | 'web'>,
  url: fc.option(fc.webUrl(), { nil: undefined }),
});

// Generate valid ISO date strings directly
const isoDateStringArbitrary = fc.integer({ min: 1577836800000, max: 1924991999999 })
  .map(timestamp => new Date(timestamp).toISOString());

// Generator for ChatMessage
const chatMessageArbitrary: fc.Arbitrary<ChatMessage> = fc.record({
  id: fc.uuid(),
  role: fc.constantFrom('user', 'assistant') as fc.Arbitrary<'user' | 'assistant'>,
  content: fc.string({ minLength: 1, maxLength: 1000 }),
  citations: fc.option(fc.array(citationArbitrary, { minLength: 0, maxLength: 5 }), { nil: undefined }),
  thoughtSteps: fc.option(fc.array(thoughtStepArbitrary, { minLength: 0, maxLength: 3 }), { nil: undefined }),
  feedback: fc.constantFrom('up', 'down', null, undefined) as fc.Arbitrary<'up' | 'down' | null | undefined>,
  timestamp: isoDateStringArbitrary,
});

// Generator for Conversation with messages
const conversationArbitrary: fc.Arbitrary<Conversation> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 100 }),
  documentIds: fc.array(fc.uuid(), { minLength: 0, maxLength: 5 }),
  messages: fc.array(chatMessageArbitrary, { minLength: 0, maxLength: 10 }),
  createdAt: isoDateStringArbitrary,
  updatedAt: isoDateStringArbitrary,
});

describe('Chat Store Property Tests', () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatStore.setState({
      conversations: [],
      currentSessionId: null,
      agentStatus: 'idle',
    });
  });

  /**
   * **Feature: frontend-redesign, Property 12: Message append preserves history**
   * **Validates: Requirements 6.3**
   *
   * For any conversation with existing messages, appending a new message
   * should preserve all previous messages and add the new one at the end.
   */
  it('addMessage preserves all existing messages and appends new message', () => {
    fc.assert(
      fc.property(
        conversationArbitrary,
        chatMessageArbitrary,
        (conversation: Conversation, newMessage: ChatMessage) => {
          // Reset state
          useChatStore.setState({
            conversations: [],
            currentSessionId: null,
            agentStatus: 'idle',
          });

          // Set up initial conversation
          useChatStore.getState().setConversations([conversation]);

          // Store original messages for comparison
          const originalMessages = [...conversation.messages];
          const originalMessageCount = originalMessages.length;

          // Add new message
          useChatStore.getState().addMessage(conversation.id, newMessage);

          // Get updated conversation
          const updatedConversation = useChatStore.getState().conversations.find(
            c => c.id === conversation.id
          );

          // Verify conversation exists
          expect(updatedConversation).toBeDefined();

          // Verify message count increased by 1
          expect(updatedConversation!.messages.length).toBe(originalMessageCount + 1);

          // Verify all original messages are preserved in order
          for (let i = 0; i < originalMessageCount; i++) {
            expect(updatedConversation!.messages[i]).toEqual(originalMessages[i]);
          }

          // Verify new message is at the end
          expect(updatedConversation!.messages[originalMessageCount]).toEqual(newMessage);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 12: Message append preserves history**
   * **Validates: Requirements 6.3**
   *
   * For any sequence of message additions, all messages should be preserved
   * in the order they were added.
   */
  it('multiple addMessage calls preserve all messages in order', () => {
    fc.assert(
      fc.property(
        conversationArbitrary,
        fc.array(chatMessageArbitrary, { minLength: 1, maxLength: 5 }),
        (conversation: Conversation, newMessages: ChatMessage[]) => {
          // Reset state
          useChatStore.setState({
            conversations: [],
            currentSessionId: null,
            agentStatus: 'idle',
          });

          // Set up initial conversation
          useChatStore.getState().setConversations([conversation]);

          // Store original messages
          const originalMessages = [...conversation.messages];

          // Add all new messages
          for (const msg of newMessages) {
            useChatStore.getState().addMessage(conversation.id, msg);
          }

          // Get updated conversation
          const updatedConversation = useChatStore.getState().conversations.find(
            c => c.id === conversation.id
          );

          // Verify total message count
          expect(updatedConversation!.messages.length).toBe(
            originalMessages.length + newMessages.length
          );

          // Verify original messages are preserved
          for (let i = 0; i < originalMessages.length; i++) {
            expect(updatedConversation!.messages[i]).toEqual(originalMessages[i]);
          }

          // Verify new messages are appended in order
          for (let i = 0; i < newMessages.length; i++) {
            expect(updatedConversation!.messages[originalMessages.length + i]).toEqual(
              newMessages[i]
            );
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 12: Message append preserves history**
   * **Validates: Requirements 6.3**
   *
   * Adding a message to one conversation should not affect other conversations.
   */
  it('addMessage to one conversation does not affect other conversations', () => {
    fc.assert(
      fc.property(
        fc.array(conversationArbitrary, { minLength: 2, maxLength: 5 }),
        chatMessageArbitrary,
        fc.nat(),
        (conversations: Conversation[], newMessage: ChatMessage, targetIndex: number) => {
          // Ensure unique conversation IDs
          const uniqueConversations = conversations.map((c, i) => ({
            ...c,
            id: `conv-${i}-${c.id}`,
          }));

          // Reset state
          useChatStore.setState({
            conversations: [],
            currentSessionId: null,
            agentStatus: 'idle',
          });

          // Set up conversations
          useChatStore.getState().setConversations(uniqueConversations);

          // Store original state of all conversations
          const originalStates = uniqueConversations.map(c => ({
            id: c.id,
            messages: [...c.messages],
          }));

          // Pick target conversation
          const targetConvIndex = targetIndex % uniqueConversations.length;
          const targetConvId = uniqueConversations[targetConvIndex].id;

          // Add message to target conversation
          useChatStore.getState().addMessage(targetConvId, newMessage);

          // Verify other conversations are unchanged
          const updatedConversations = useChatStore.getState().conversations;
          for (let i = 0; i < originalStates.length; i++) {
            const updated = updatedConversations.find(c => c.id === originalStates[i].id);
            expect(updated).toBeDefined();

            if (i !== targetConvIndex) {
              // Non-target conversations should be unchanged
              expect(updated!.messages).toEqual(originalStates[i].messages);
            } else {
              // Target conversation should have new message
              expect(updated!.messages.length).toBe(originalStates[i].messages.length + 1);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
