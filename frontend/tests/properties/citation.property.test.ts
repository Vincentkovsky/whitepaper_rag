/**
 * Property-Based Tests for Citation Parsing
 * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
 * **Validates: Requirements 3.5**
 *
 * Property: For any answer string containing citation markers [[citation:doc_id:chunk_id]],
 * the output should contain clickable badges with correct indices.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { 
  parseCitations, 
  hasCitations, 
  countUniqueCitations,
  toCitationObjects,
  type ParsedCitation 
} from '../../src/utils/citationParser';

// Generator for valid document IDs (alphanumeric, no colons or brackets)
const documentIdArbitrary = fc.stringMatching(/^[a-zA-Z0-9_-]{1,36}$/);

// Generator for valid chunk IDs (alphanumeric, no colons or brackets)
const chunkIdArbitrary = fc.stringMatching(/^[a-zA-Z0-9_-]{1,36}$/);

// Generator for a single citation marker
const citationMarkerArbitrary = fc.tuple(documentIdArbitrary, chunkIdArbitrary)
  .map(([docId, chunkId]) => `[[citation:${docId}:${chunkId}]]`);

// Generator for text without citation markers
const plainTextArbitrary = fc.string({ minLength: 0, maxLength: 200 })
  .filter(s => !s.includes('[[citation:'));

// Generator for text with embedded citations
const textWithCitationsArbitrary = fc.tuple(
  plainTextArbitrary,
  fc.array(
    fc.tuple(documentIdArbitrary, chunkIdArbitrary, plainTextArbitrary),
    { minLength: 1, maxLength: 5 }
  )
).map(([prefix, citations]) => {
  let text = prefix;
  for (const [docId, chunkId, suffix] of citations) {
    text += `[[citation:${docId}:${chunkId}]]${suffix}`;
  }
  return { text, expectedCount: citations.length };
});

describe('Citation Parsing Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * For any text with citation markers, parseCitations should extract all citations
   * with correct documentId and chunkId.
   */
  it('extracts all citation markers with correct document and chunk IDs', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(documentIdArbitrary, chunkIdArbitrary), { minLength: 1, maxLength: 5 }),
        (citationPairs) => {
          // Build text with citations
          const text = citationPairs
            .map(([docId, chunkId]) => `See [[citation:${docId}:${chunkId}]] here.`)
            .join(' ');
          
          const result = parseCitations(text);
          
          // Should find all citations
          expect(result.citations.length).toBe(citationPairs.length);
          
          // Each citation should have correct IDs
          for (let i = 0; i < citationPairs.length; i++) {
            const [expectedDocId, expectedChunkId] = citationPairs[i];
            const citation = result.citations[i];
            expect(citation.documentId).toBe(expectedDocId);
            expect(citation.chunkId).toBe(expectedChunkId);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * For any text with citations, the processed text should replace markers with [n] badges.
   */
  it('replaces citation markers with numbered badges [n]', () => {
    fc.assert(
      fc.property(
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        ([docId, chunkId]) => {
          const text = `Reference [[citation:${docId}:${chunkId}]] in document.`;
          const result = parseCitations(text);
          
          // Processed text should contain [1] instead of the marker
          expect(result.processedText).toContain('[1]');
          expect(result.processedText).not.toContain('[[citation:');
          expect(result.processedText).toBe('Reference [1] in document.');
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * Duplicate citations (same doc_id:chunk_id) should receive the same index.
   */
  it('assigns same index to duplicate citations', () => {
    fc.assert(
      fc.property(
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        ([docId, chunkId]) => {
          const text = `First [[citation:${docId}:${chunkId}]] and second [[citation:${docId}:${chunkId}]].`;
          const result = parseCitations(text);
          
          // Should find 2 citations
          expect(result.citations.length).toBe(2);
          
          // Both should have the same index
          expect(result.citations[0].index).toBe(result.citations[1].index);
          expect(result.citations[0].index).toBe(1);
          
          // Processed text should have two [1] badges
          expect(result.processedText).toBe('First [1] and second [1].');
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * Different citations should receive different sequential indices.
   */
  it('assigns sequential indices to different citations', () => {
    fc.assert(
      fc.property(
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        ([docId1, chunkId1], [docId2, chunkId2]) => {
          // Ensure they're different
          fc.pre(docId1 !== docId2 || chunkId1 !== chunkId2);
          
          const text = `First [[citation:${docId1}:${chunkId1}]] and second [[citation:${docId2}:${chunkId2}]].`;
          const result = parseCitations(text);
          
          // Should find 2 citations with indices 1 and 2
          expect(result.citations.length).toBe(2);
          expect(result.citations[0].index).toBe(1);
          expect(result.citations[1].index).toBe(2);
          
          // Processed text should have [1] and [2]
          expect(result.processedText).toBe('First [1] and second [2].');
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * Text without citations should return empty citations array and unchanged text.
   */
  it('returns empty citations for text without markers', () => {
    fc.assert(
      fc.property(plainTextArbitrary, (text) => {
        const result = parseCitations(text);
        
        expect(result.citations).toHaveLength(0);
        expect(result.processedText).toBe(text);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * hasCitations should return true iff text contains citation markers.
   */
  it('hasCitations correctly detects presence of citations', () => {
    fc.assert(
      fc.property(
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        plainTextArbitrary,
        ([docId, chunkId], plainText) => {
          const textWithCitation = `${plainText}[[citation:${docId}:${chunkId}]]`;
          
          expect(hasCitations(textWithCitation)).toBe(true);
          expect(hasCitations(plainText)).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * countUniqueCitations should return correct count of unique citations.
   */
  it('countUniqueCitations returns correct unique count', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(documentIdArbitrary, chunkIdArbitrary), { minLength: 1, maxLength: 5 }),
        (citationPairs) => {
          // Build text with citations (may have duplicates)
          const text = citationPairs
            .map(([docId, chunkId]) => `[[citation:${docId}:${chunkId}]]`)
            .join(' ');
          
          // Calculate expected unique count
          const uniqueKeys = new Set(citationPairs.map(([d, c]) => `${d}:${c}`));
          const expectedCount = uniqueKeys.size;
          
          expect(countUniqueCitations(text)).toBe(expectedCount);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * Citation indices should be 1-based and sequential.
   */
  it('citation indices are 1-based and sequential', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(documentIdArbitrary, chunkIdArbitrary), { minLength: 1, maxLength: 10 }),
        (citationPairs) => {
          // Ensure all unique
          const uniquePairs = [...new Map(citationPairs.map(p => [`${p[0]}:${p[1]}`, p])).values()];
          
          const text = uniquePairs
            .map(([docId, chunkId]) => `[[citation:${docId}:${chunkId}]]`)
            .join(' ');
          
          const result = parseCitations(text);
          
          // Get unique indices
          const indices = [...new Set(result.citations.map(c => c.index))].sort((a, b) => a - b);
          
          // Should be 1, 2, 3, ... n
          for (let i = 0; i < indices.length; i++) {
            expect(indices[i]).toBe(i + 1);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * toCitationObjects should produce Citation objects with correct fields.
   */
  it('toCitationObjects creates valid Citation objects', () => {
    fc.assert(
      fc.property(
        fc.array(fc.tuple(documentIdArbitrary, chunkIdArbitrary), { minLength: 1, maxLength: 5 }),
        (citationPairs) => {
          const text = citationPairs
            .map(([docId, chunkId]) => `[[citation:${docId}:${chunkId}]]`)
            .join(' ');
          
          const { citations: parsed } = parseCitations(text);
          const citationObjects = toCitationObjects(parsed, {
            text: 'Sample text',
            textSnippet: 'snippet',
            sourceType: 'pdf',
          });
          
          // Should have unique citations only
          const uniqueKeys = new Set(citationPairs.map(([d, c]) => `${d}:${c}`));
          expect(citationObjects.length).toBe(uniqueKeys.size);
          
          // Each should have required fields
          for (const citation of citationObjects) {
            expect(citation.index).toBeGreaterThanOrEqual(1);
            expect(citation.documentId).toBeTruthy();
            expect(citation.chunkId).toBeTruthy();
            expect(citation.text).toBe('Sample text');
            expect(citation.textSnippet).toBe('snippet');
            expect(citation.sourceType).toBe('pdf');
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 5: Citation parsing and rendering**
   * **Validates: Requirements 3.5**
   *
   * Parsed citation positions (startIndex, endIndex) should be correct.
   */
  it('citation positions are accurate', () => {
    fc.assert(
      fc.property(
        fc.tuple(documentIdArbitrary, chunkIdArbitrary),
        plainTextArbitrary,
        ([docId, chunkId], prefix) => {
          const marker = `[[citation:${docId}:${chunkId}]]`;
          const text = `${prefix}${marker}`;
          
          const result = parseCitations(text);
          
          expect(result.citations.length).toBe(1);
          const citation = result.citations[0];
          
          expect(citation.startIndex).toBe(prefix.length);
          expect(citation.endIndex).toBe(prefix.length + marker.length);
          expect(citation.fullMatch).toBe(marker);
        }
      ),
      { numRuns: 100 }
    );
  });
});
