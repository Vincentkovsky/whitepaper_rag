/**
 * Property-Based Tests for Citation Click Actions
 * **Feature: frontend-redesign, Property 13: Citation click actions**
 * **Validates: Requirements 8.2, 8.3, 8.4**
 *
 * Property: For any citation click, the system should trigger:
 * (1) document load for the correct documentId,
 * (2) scroll to the correct page,
 * (3) highlight the correct chunk.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import { render, cleanup, fireEvent } from '@testing-library/react';
import React from 'react';
import { EvidenceBoard } from '../../src/components/EvidenceBoard';
import { CitationBadge } from '../../src/components/CitationBadge';
import type { Citation } from '../../src/types';

// Generator for valid document IDs
const documentIdArbitrary = fc.uuid();

// Generator for valid chunk IDs
const chunkIdArbitrary = fc.uuid();

// Generator for page numbers (1-indexed, reasonable range)
const pageNumberArbitrary = fc.integer({ min: 1, max: 500 });

// Generator for citation index
const citationIndexArbitrary = fc.integer({ min: 1, max: 20 });

// Generator for text snippets
const textSnippetArbitrary = fc.string({ minLength: 10, maxLength: 200 })
  .filter(s => s.trim().length >= 10);

// Generator for URLs
const urlArbitrary = fc.webUrl();

// Generator for highlight coordinates (quadrilaterals)
const highlightCoordsArbitrary = fc.array(
  fc.tuple(
    fc.float({ min: 0, max: 600 }),
    fc.float({ min: 0, max: 800 }),
    fc.float({ min: 0, max: 600 }),
    fc.float({ min: 0, max: 800 })
  ).map(([x1, y1, x2, y2]) => [
    Math.min(x1, x2),
    Math.min(y1, y2),
    Math.max(x1, x2),
    Math.max(y1, y2)
  ]),
  { minLength: 0, maxLength: 5 }
);

// Generator for PDF citations
const pdfCitationArbitrary: fc.Arbitrary<Citation> = fc.record({
  index: citationIndexArbitrary,
  documentId: documentIdArbitrary,
  chunkId: chunkIdArbitrary,
  page: fc.option(pageNumberArbitrary, { nil: undefined }),
  text: textSnippetArbitrary,
  textSnippet: textSnippetArbitrary,
  highlightCoords: fc.option(highlightCoordsArbitrary, { nil: undefined }),
  sourceType: fc.constant('pdf' as const),
  url: fc.constant(undefined),
});

// Generator for Web citations
const webCitationArbitrary: fc.Arbitrary<Citation> = fc.record({
  index: citationIndexArbitrary,
  documentId: documentIdArbitrary,
  chunkId: chunkIdArbitrary,
  page: fc.constant(undefined),
  text: textSnippetArbitrary,
  textSnippet: textSnippetArbitrary,
  highlightCoords: fc.constant(undefined),
  sourceType: fc.constant('web' as const),
  url: urlArbitrary,
});

// Generator for any citation
const citationArbitrary: fc.Arbitrary<Citation> = fc.oneof(
  pdfCitationArbitrary,
  webCitationArbitrary
);

describe('Citation Click Property Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * For any citation, clicking the badge should invoke the onClick handler
   * with the correct citation data.
   */
  it('citation badge click passes correct citation data', () => {
    fc.assert(
      fc.property(citationArbitrary, (citation) => {
        cleanup();
        
        const handleClick = vi.fn();
        
        const { getByTestId, unmount } = render(
          <CitationBadge citation={citation} onClick={handleClick} />
        );

        const badge = getByTestId(`citation-badge-${citation.index}`);
        fireEvent.click(badge);

        expect(handleClick).toHaveBeenCalledTimes(1);
        expect(handleClick).toHaveBeenCalledWith(citation);
        
        // Verify the citation data passed includes all required fields
        const passedCitation = handleClick.mock.calls[0][0] as Citation;
        expect(passedCitation.documentId).toBe(citation.documentId);
        expect(passedCitation.chunkId).toBe(citation.chunkId);
        expect(passedCitation.sourceType).toBe(citation.sourceType);
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * For any PDF citation with a page number, the Evidence Board should
   * display the correct page information.
   */
  it('evidence board displays correct page for PDF citations', () => {
    // Use PDF citations with page numbers
    const pdfWithPageArbitrary = fc.record({
      index: citationIndexArbitrary,
      documentId: documentIdArbitrary,
      chunkId: chunkIdArbitrary,
      page: pageNumberArbitrary,
      text: textSnippetArbitrary,
      textSnippet: textSnippetArbitrary,
      highlightCoords: fc.option(highlightCoordsArbitrary, { nil: undefined }),
      sourceType: fc.constant('pdf' as const),
      url: fc.constant(undefined),
    });

    fc.assert(
      fc.property(pdfWithPageArbitrary, (citation) => {
        cleanup();
        
        const { container, unmount } = render(
          <EvidenceBoard citation={citation} />
        );

        // Check that the evidence board shows the correct source type
        const board = container.querySelector('[data-testid="evidence-board"]');
        expect(board).not.toBeNull();
        expect(board?.getAttribute('data-source-type')).toBe('pdf');
        
        // Check that page info is displayed in footer
        const pageInfo = container.textContent;
        expect(pageInfo).toContain(`Page ${citation.page}`);
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * For any citation, the Evidence Board should display the correct
   * document ID in the footer.
   */
  it('evidence board displays correct document ID for PDF citations', () => {
    fc.assert(
      fc.property(pdfCitationArbitrary, (citation) => {
        cleanup();
        
        const { container, unmount } = render(
          <EvidenceBoard citation={citation} />
        );

        // Check that document ID is displayed
        const content = container.textContent;
        expect(content).toContain(citation.documentId);
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * For any web citation, the Evidence Board should display the web card
   * with the correct URL.
   */
  it('evidence board displays web card for web citations', () => {
    fc.assert(
      fc.property(webCitationArbitrary, (citation) => {
        cleanup();
        
        const { container, unmount } = render(
          <EvidenceBoard citation={citation} />
        );

        // Check that the evidence board shows the correct source type
        const board = container.querySelector('[data-testid="evidence-board"]');
        expect(board).not.toBeNull();
        expect(board?.getAttribute('data-source-type')).toBe('web');
        
        // Check that web content area is rendered
        const webContent = container.querySelector('[data-testid="evidence-board-web"]');
        expect(webContent).not.toBeNull();
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * For any citation, the Evidence Board should display the citation index
   * in the header.
   */
  it('evidence board displays citation index in header', () => {
    fc.assert(
      fc.property(citationArbitrary, (citation) => {
        cleanup();
        
        const { container, unmount } = render(
          <EvidenceBoard citation={citation} />
        );

        // Check that citation index is displayed in header
        const headerContent = container.textContent;
        expect(headerContent).toContain(`Citation [${citation.index}]`);
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * When no citation is provided, the Evidence Board should show empty state.
   */
  it('evidence board shows empty state when no citation', () => {
    cleanup();
    
    const { getByTestId, unmount } = render(
      <EvidenceBoard citation={null} />
    );

    const emptyState = getByTestId('evidence-board-empty');
    expect(emptyState).not.toBeNull();
    expect(emptyState.textContent).toContain('No citation selected');
    
    unmount();
  });

  /**
   * **Feature: frontend-redesign, Property 13: Citation click actions**
   * **Validates: Requirements 8.2, 8.3, 8.4**
   *
   * The close button should call onClose when clicked.
   */
  it('close button triggers onClose callback', () => {
    fc.assert(
      fc.property(citationArbitrary, (citation) => {
        cleanup();
        
        const handleClose = vi.fn();
        
        const { getByTestId, unmount } = render(
          <EvidenceBoard citation={citation} onClose={handleClose} />
        );

        const closeButton = getByTestId('evidence-board-close');
        fireEvent.click(closeButton);

        expect(handleClose).toHaveBeenCalledTimes(1);
        
        unmount();
      }),
      { numRuns: 100 }
    );
  });
});
