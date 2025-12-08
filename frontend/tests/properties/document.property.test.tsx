/**
 * Property-Based Tests for Document List Rendering
 * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
 * **Validates: Requirements 2.3**
 *
 * Property: For any list of documents, the rendered output should contain
 * the name, status, and upload date for each document.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { render, screen, cleanup, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DocumentList } from '../../src/components/DocumentList';
import { useDocumentStore } from '../../src/stores/documentStore';
import type { Document, DocumentStatus } from '../../src/types';

// Generator for DocumentStatus - only use 'ready' and 'failed' to avoid polling side effects
const documentStatusArbitrary: fc.Arbitrary<DocumentStatus> = fc.constantFrom(
  'ready',
  'failed'
);

// Generate valid ISO date strings
const isoDateStringArbitrary = fc
  .integer({ min: 1577836800000, max: 1924991999999 })
  .map((timestamp) => new Date(timestamp).toISOString());

// Generator for Document with unique names to avoid collision
const documentArbitrary = (index: number): fc.Arbitrary<Document> => fc.record({
  id: fc.uuid().map(id => `doc-${index}-${id}`),
  name: fc.string({ minLength: 3, maxLength: 50 })
    .filter((s) => s.trim().length >= 3 && /^[a-zA-Z0-9]/.test(s))
    .map(s => `Doc${index}_${s}`),
  status: documentStatusArbitrary,
  errorMessage: fc.option(
    fc.string({ minLength: 5, maxLength: 100 }).filter((s) => s.trim().length >= 5),
    { nil: undefined }
  ),
  createdAt: isoDateStringArbitrary,
  pageCount: fc.option(fc.nat({ max: 1000 }), { nil: undefined }),
});

// Generator for non-empty array of documents with unique names
const documentsArbitrary: fc.Arbitrary<Document[]> = fc
  .integer({ min: 1, max: 5 })
  .chain((count) =>
    fc.tuple(...Array.from({ length: count }, (_, i) => documentArbitrary(i)))
  );

/**
 * Format date the same way the component does for comparison
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Get expected status text
 */
function getExpectedStatusText(status: DocumentStatus): string {
  switch (status) {
    case 'ready':
      return 'Ready';
    case 'processing':
      return 'Processing';
    case 'pending':
      return 'Pending';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

/**
 * Wrapper component for testing
 */
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

describe('Document List Property Tests', () => {
  beforeEach(() => {
    // Reset store state before each test
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: false,
    });
  });

  afterEach(() => {
    cleanup();
    // Reset store state after each test
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: false,
    });
  });

  /**
   * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
   * **Validates: Requirements 2.3**
   *
   * For any list of documents, the rendered output should contain
   * the name, status, and upload date for each document.
   */
  it('renders document name, status, and upload date for each document', () => {
    fc.assert(
      fc.property(documentsArbitrary, (documents: Document[]) => {
        // Clean up any previous renders
        cleanup();
        
        // Reset and set up store with documents
        useDocumentStore.setState({
          documents,
          selectedDocumentId: null,
          uploadProgress: new Map(),
          isLoading: false,
        });

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <DocumentList />
          </TestWrapper>
        );

        // Get the list element
        const list = container.querySelector('[role="list"]');
        expect(list).not.toBeNull();

        // Get all list items
        const listItems = container.querySelectorAll('[role="listitem"]');
        expect(listItems.length).toBe(documents.length);

        // Verify each document's information is rendered
        for (let i = 0; i < documents.length; i++) {
          const doc = documents[i];
          const listItem = listItems[i];
          
          // Check document name is rendered within this list item
          expect(listItem.textContent).toContain(doc.name);

          // Check status is rendered
          const statusText = getExpectedStatusText(doc.status);
          expect(listItem.textContent).toContain(statusText);

          // Check date is rendered
          const formattedDate = formatDate(doc.createdAt);
          expect(listItem.textContent).toContain(formattedDate);
        }

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
   * **Validates: Requirements 2.3**
   *
   * The number of rendered document items should match the number of documents.
   */
  it('renders correct number of document items', () => {
    fc.assert(
      fc.property(documentsArbitrary, (documents: Document[]) => {
        // Clean up any previous renders
        cleanup();
        
        // Reset and set up store with documents
        useDocumentStore.setState({
          documents,
          selectedDocumentId: null,
          uploadProgress: new Map(),
          isLoading: false,
        });

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <DocumentList />
          </TestWrapper>
        );

        // Get all list items
        const listItems = container.querySelectorAll('[role="listitem"]');
        expect(listItems.length).toBe(documents.length);

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
   * **Validates: Requirements 2.3**
   *
   * Failed documents should display their error message.
   */
  it('renders error message for failed documents', () => {
    // Generate documents that are specifically failed with error messages
    const failedDocumentArbitrary = (index: number): fc.Arbitrary<Document> => fc.record({
      id: fc.uuid().map(id => `failed-doc-${index}-${id}`),
      name: fc.string({ minLength: 3, maxLength: 50 })
        .filter((s) => s.trim().length >= 3 && /^[a-zA-Z0-9]/.test(s))
        .map(s => `FailedDoc${index}_${s}`),
      status: fc.constant('failed' as DocumentStatus),
      errorMessage: fc.string({ minLength: 5, maxLength: 100 })
        .filter((s) => s.trim().length >= 5)
        .map(s => `Error${index}_${s}`),
      createdAt: isoDateStringArbitrary,
      pageCount: fc.option(fc.nat({ max: 1000 }), { nil: undefined }),
    });

    const failedDocumentsArbitrary: fc.Arbitrary<Document[]> = fc
      .integer({ min: 1, max: 3 })
      .chain((count) =>
        fc.tuple(...Array.from({ length: count }, (_, i) => failedDocumentArbitrary(i)))
      );

    fc.assert(
      fc.property(failedDocumentsArbitrary, (documents: Document[]) => {
        // Clean up any previous renders
        cleanup();
        
        // Reset and set up store with failed documents
        useDocumentStore.setState({
          documents,
          selectedDocumentId: null,
          uploadProgress: new Map(),
          isLoading: false,
        });

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <DocumentList />
          </TestWrapper>
        );

        // Get all list items
        const listItems = container.querySelectorAll('[role="listitem"]');

        // Verify each failed document's error message is rendered
        for (let i = 0; i < documents.length; i++) {
          const doc = documents[i];
          const listItem = listItems[i];
          
          if (doc.errorMessage) {
            expect(listItem.textContent).toContain(doc.errorMessage);
          }
        }

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
   * **Validates: Requirements 2.3**
   *
   * Empty document list should show empty state message.
   */
  it('renders empty state when no documents', () => {
    // Clean up any previous renders
    cleanup();
    
    // Set up store with no documents
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: false,
    });

    // Render the component
    const { unmount } = render(
      <TestWrapper>
        <DocumentList />
      </TestWrapper>
    );

    // Check for empty state message
    expect(screen.getByText('No documents yet')).toBeDefined();
    expect(screen.getByText('Upload a PDF or submit a URL to get started')).toBeDefined();
    
    unmount();
  });

  /**
   * **Feature: frontend-redesign, Property 2: Document list rendering completeness**
   * **Validates: Requirements 2.3**
   *
   * Loading state should show skeleton loaders.
   */
  it('renders skeleton loaders when loading', () => {
    // Clean up any previous renders
    cleanup();
    
    // Set up store in loading state
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: true,
    });

    // Render the component
    const { container, unmount } = render(
      <TestWrapper>
        <DocumentList />
      </TestWrapper>
    );

    // Check for skeleton loaders (elements with animate-pulse class)
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
    
    unmount();
  });
});
