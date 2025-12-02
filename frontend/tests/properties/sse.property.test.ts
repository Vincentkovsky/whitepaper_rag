/**
 * Property-Based Tests for SSE Event Parsing
 * **Feature: frontend-redesign, Property 4: SSE event rendering**
 * **Validates: Requirements 3.2, 3.3**
 *
 * Property: For any valid SSE event (thinking, tool_call, tool_result, answer),
 * the parseSSEEvent function should return the correct event type with proper fields.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { parseSSEEvent } from '../../src/services/sseClient';
import type { Citation } from '../../src/types';

// Generator for finite floats (JSON-serializable, no Infinity/NaN)
const finiteFloatArbitrary = fc.double({ 
  min: -1e10, 
  max: 1e10, 
  noNaN: true 
});

// Generator for Citation objects (used in answer events)
// Note: We use JSON-serializable values only since SSE events go through JSON.stringify/parse
const citationArbitrary: fc.Arbitrary<Citation> = fc.record({
  index: fc.nat({ max: 100 }),
  documentId: fc.uuid(),
  chunkId: fc.uuid(),
  page: fc.option(fc.nat({ max: 1000 }), { nil: undefined }),
  text: fc.string({ minLength: 1, maxLength: 500 }),
  textSnippet: fc.string({ minLength: 1, maxLength: 200 }),
  highlightCoords: fc.option(
    fc.array(fc.array(finiteFloatArbitrary, { minLength: 4, maxLength: 4 })), 
    { nil: undefined }
  ),
  sourceType: fc.constantFrom('pdf', 'web') as fc.Arbitrary<'pdf' | 'web'>,
  url: fc.option(fc.webUrl(), { nil: undefined }),
});

// Generator for thinking event data
const thinkingEventDataArbitrary = fc.record({
  type: fc.constant('thinking'),
  content: fc.string({ minLength: 0, maxLength: 1000 }),
});

// Generator for tool_call event data
const toolCallEventDataArbitrary = fc.record({
  type: fc.constant('tool_call'),
  tool: fc.string({ minLength: 1, maxLength: 100 }),
  input: fc.jsonValue(),
});

// Generator for tool_result event data
const toolResultEventDataArbitrary = fc.record({
  type: fc.constant('tool_result'),
  tool: fc.string({ minLength: 1, maxLength: 100 }),
  result: fc.jsonValue(),
});

// Generator for answer event data
const answerEventDataArbitrary = fc.record({
  type: fc.constant('answer'),
  content: fc.string({ minLength: 0, maxLength: 2000 }),
  sources: fc.option(fc.array(citationArbitrary, { minLength: 0, maxLength: 5 }), { nil: undefined }),
});

// Generator for error event data
const errorEventDataArbitrary = fc.record({
  type: fc.constant('error'),
  message: fc.string({ minLength: 0, maxLength: 500 }),
});

// Generator for done event data
const doneEventDataArbitrary = fc.record({
  type: fc.constant('done'),
});

describe('SSE Event Parsing Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid thinking event JSON, parseSSEEvent should return
   * an event with type 'thinking' and the correct content.
   */
  it('parses thinking events correctly for any valid content', () => {
    fc.assert(
      fc.property(thinkingEventDataArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('thinking');
        expect((result as { type: 'thinking'; content: string }).content).toBe(eventData.content);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid tool_call event JSON, parseSSEEvent should return
   * an event with type 'tool_call' and the correct tool name and input.
   */
  it('parses tool_call events correctly for any valid tool and input', () => {
    fc.assert(
      fc.property(toolCallEventDataArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('tool_call');
        
        const toolCallResult = result as { type: 'tool_call'; tool: string; input: unknown };
        expect(toolCallResult.tool).toBe(eventData.tool);
        // Compare after JSON round-trip to handle -0 vs +0 edge case
        // JSON.stringify(-0) produces "0", so -0 doesn't round-trip through JSON
        const expectedInput = JSON.parse(JSON.stringify(eventData.input));
        expect(toolCallResult.input).toEqual(expectedInput);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid tool_result event JSON, parseSSEEvent should return
   * an event with type 'tool_result' and the correct tool name and result.
   */
  it('parses tool_result events correctly for any valid tool and result', () => {
    fc.assert(
      fc.property(toolResultEventDataArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('tool_result');
        
        const toolResultEvent = result as { type: 'tool_result'; tool: string; result: unknown };
        expect(toolResultEvent.tool).toBe(eventData.tool);
        // Compare after JSON round-trip to handle -0 vs +0 edge case
        const expectedResult = JSON.parse(JSON.stringify(eventData.result));
        expect(toolResultEvent.result).toEqual(expectedResult);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid answer event JSON, parseSSEEvent should return
   * an event with type 'answer' and the correct content and sources.
   */
  it('parses answer events correctly for any valid content and sources', () => {
    fc.assert(
      fc.property(answerEventDataArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('answer');
        
        const answerResult = result as { type: 'answer'; content: string; sources?: Citation[] };
        expect(answerResult.content).toBe(eventData.content);
        
        // Compare sources after JSON round-trip to account for undefined stripping
        // JSON.parse(JSON.stringify(x)) normalizes undefined values
        const expectedSources = eventData.sources 
          ? JSON.parse(JSON.stringify(eventData.sources)) 
          : eventData.sources;
        expect(answerResult.sources).toEqual(expectedSources);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid error event JSON, parseSSEEvent should return
   * an event with type 'error' and the correct message.
   */
  it('parses error events correctly for any valid message', () => {
    fc.assert(
      fc.property(errorEventDataArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('error');
        
        const errorResult = result as { type: 'error'; message: string };
        // Note: empty message defaults to 'Unknown error' in parseSSEEvent
        const expectedMessage = eventData.message || 'Unknown error';
        expect(errorResult.message).toBe(expectedMessage);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid done event JSON, parseSSEEvent should return
   * an event with type 'done'.
   */
  it('parses done events correctly', () => {
    fc.assert(
      fc.property(doneEventDataArbitrary, () => {
        const jsonString = JSON.stringify({ type: 'done' });
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe('done');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any invalid JSON string, parseSSEEvent should return null.
   */
  it('returns null for invalid JSON', () => {
    fc.assert(
      fc.property(
        fc.string().filter(s => {
          try {
            JSON.parse(s);
            return false; // Valid JSON, filter out
          } catch {
            return true; // Invalid JSON, keep
          }
        }),
        (invalidJson) => {
          const result = parseSSEEvent(invalidJson);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any JSON object without a 'type' field, parseSSEEvent should return null.
   */
  it('returns null for JSON without type field', () => {
    fc.assert(
      fc.property(
        fc.record({
          content: fc.string(),
          data: fc.jsonValue(),
        }),
        (dataWithoutType) => {
          const jsonString = JSON.stringify(dataWithoutType);
          const result = parseSSEEvent(jsonString);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any JSON object with an unknown type, parseSSEEvent should return null.
   */
  it('returns null for unknown event types', () => {
    fc.assert(
      fc.property(
        fc.record({
          type: fc.string().filter(t => 
            !['thinking', 'tool_call', 'tool_result', 'answer', 'error', 'done'].includes(t)
          ),
          content: fc.string(),
        }),
        (unknownTypeData) => {
          const jsonString = JSON.stringify(unknownTypeData);
          const result = parseSSEEvent(jsonString);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 4: SSE event rendering**
   * **Validates: Requirements 3.2, 3.3**
   *
   * For any valid SSE event type, the parsed result type should match the input type.
   * This is a comprehensive test covering all event types.
   */
  it('event type in output matches event type in input for all valid events', () => {
    const allEventTypesArbitrary = fc.oneof(
      thinkingEventDataArbitrary,
      toolCallEventDataArbitrary,
      toolResultEventDataArbitrary,
      answerEventDataArbitrary,
      errorEventDataArbitrary,
      doneEventDataArbitrary
    );

    fc.assert(
      fc.property(allEventTypesArbitrary, (eventData) => {
        const jsonString = JSON.stringify(eventData);
        const result = parseSSEEvent(jsonString);

        expect(result).not.toBeNull();
        expect(result!.type).toBe(eventData.type);
      }),
      { numRuns: 100 }
    );
  });
});
