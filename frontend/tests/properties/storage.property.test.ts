/**
 * Property-Based Tests for Storage Service
 * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
 * **Validates: Requirements 6.4, 7.2, 7.3**
 *
 * Property: For any conversation object, serializing to localStorage and
 * deserializing should produce an equivalent object.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { storageService } from '../../src/services/storageService';
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

// Generator for Conversation
const conversationArbitrary: fc.Arbitrary<Conversation> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 100 }),
  documentIds: fc.array(fc.uuid(), { minLength: 0, maxLength: 5 }),
  messages: fc.array(chatMessageArbitrary, { minLength: 0, maxLength: 10 }),
  createdAt: isoDateStringArbitrary,
  updatedAt: isoDateStringArbitrary,
});

describe('Storage Service Property Tests', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    storageService.clearAll();
  });

  afterEach(() => {
    // Clean up after each test
    storageService.clearAll();
  });

  /**
   * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
   * **Validates: Requirements 6.4, 7.2, 7.3**
   *
   * For any single conversation, saving and loading should produce an equivalent object.
   */
  it('single conversation round-trip preserves data', () => {
    fc.assert(
      fc.property(
        conversationArbitrary,
        (conversation: Conversation) => {
          // Clear storage
          storageService.clearAll();

          // Save conversation
          storageService.saveConversations([conversation]);

          // Load conversation
          const loaded = storageService.loadConversations();

          // Verify exactly one conversation loaded
          expect(loaded.length).toBe(1);

          // Verify conversation data is equivalent
          const loadedConv = loaded[0];
          expect(loadedConv.id).toBe(conversation.id);
          expect(loadedConv.title).toBe(conversation.title);
          expect(loadedConv.documentIds).toEqual(conversation.documentIds);
          expect(loadedConv.createdAt).toBe(conversation.createdAt);
          expect(loadedConv.updatedAt).toBe(conversation.updatedAt);
          expect(loadedConv.messages.length).toBe(conversation.messages.length);

          // Verify each message
          for (let i = 0; i < conversation.messages.length; i++) {
            const original = conversation.messages[i];
            const loaded = loadedConv.messages[i];
            
            expect(loaded.id).toBe(original.id);
            expect(loaded.role).toBe(original.role);
            expect(loaded.content).toBe(original.content);
            expect(loaded.timestamp).toBe(original.timestamp);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
   * **Validates: Requirements 6.4, 7.2, 7.3**
   *
   * For any array of conversations, saving and loading should preserve all conversations.
   */
  it('multiple conversations round-trip preserves all data', () => {
    fc.assert(
      fc.property(
        fc.array(conversationArbitrary, { minLength: 0, maxLength: 10 }),
        (conversations: Conversation[]) => {
          // Clear storage
          storageService.clearAll();

          // Save conversations
          storageService.saveConversations(conversations);

          // Load conversations
          const loaded = storageService.loadConversations();

          // Verify count matches
          expect(loaded.length).toBe(conversations.length);

          // Verify each conversation is preserved
          for (let i = 0; i < conversations.length; i++) {
            const original = conversations[i];
            const loadedConv = loaded[i];

            expect(loadedConv.id).toBe(original.id);
            expect(loadedConv.title).toBe(original.title);
            expect(loadedConv.documentIds).toEqual(original.documentIds);
            expect(loadedConv.messages.length).toBe(original.messages.length);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
   * **Validates: Requirements 6.4, 7.2, 7.3**
   *
   * Saving conversations should be idempotent - saving the same data twice
   * should produce the same result when loaded.
   */
  it('saving conversations is idempotent', () => {
    fc.assert(
      fc.property(
        fc.array(conversationArbitrary, { minLength: 1, maxLength: 5 }),
        (conversations: Conversation[]) => {
          // Clear storage
          storageService.clearAll();

          // Save once
          storageService.saveConversations(conversations);
          const firstLoad = storageService.loadConversations();

          // Save again (same data)
          storageService.saveConversations(conversations);
          const secondLoad = storageService.loadConversations();

          // Results should be identical
          expect(secondLoad.length).toBe(firstLoad.length);
          
          for (let i = 0; i < firstLoad.length; i++) {
            expect(secondLoad[i].id).toBe(firstLoad[i].id);
            expect(secondLoad[i].title).toBe(firstLoad[i].title);
            expect(secondLoad[i].messages.length).toBe(firstLoad[i].messages.length);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
   * **Validates: Requirements 6.4, 7.2, 7.3**
   *
   * Empty conversations array should round-trip correctly.
   */
  it('empty conversations array round-trips correctly', () => {
    // Clear storage
    storageService.clearAll();

    // Save empty array
    storageService.saveConversations([]);

    // Load should return empty array
    const loaded = storageService.loadConversations();
    expect(loaded).toEqual([]);
  });

  /**
   * **Feature: frontend-redesign, Property 11: Conversation persistence round-trip**
   * **Validates: Requirements 7.3**
   *
   * Loading from empty/uninitialized storage should return empty array.
   */
  it('loading from empty storage returns empty array', () => {
    // Clear storage
    storageService.clearAll();

    // Load without saving anything
    const loaded = storageService.loadConversations();
    expect(loaded).toEqual([]);
  });
});
