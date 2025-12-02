/**
 * Property-Based Tests for Error Message Display
 * **Feature: frontend-redesign, Property 3: Error message display**
 * **Validates: Requirements 2.6, 3.7, 5.3**
 *
 * Property: For any error response from the API, the UI should display
 * an error message containing the error details.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { useUIStore, type Toast, type ToastType } from '../../src/stores/uiStore';
import { useDocumentStore } from '../../src/stores/documentStore';
import { DocumentList } from '../../src/components/DocumentList';
import type { Document, DocumentStatus } from '../../src/types';

// Generator for error messages
const errorMessageArbitrary: fc.Arbitrary<string> = fc
  .string({ minLength: 5, maxLength: 200 })
  .filter((s) => s.trim().length >= 5)
  .map((s) => `Error_${s.replace(/[<>]/g, '')}`);

// Generator for ToastType
const toastTypeArbitrary: fc.Arbitrary<ToastType> = fc.constantFrom(
  'success',
  'error',
  'warning',
  'info'
);

// Generator for Toast
const toastArbitrary: fc.Arbitrary<Toast> = fc.record({
  id: fc.uuid().map((id) => `toast-${id}`),
  type: toastTypeArbitrary,
  message: errorMessageArbitrary,
  duration: fc.option(fc.nat({ max: 10000 }), { nil: undefined }),
});

// Generator for error Toast specifically
const errorToastArbitrary: fc.Arbitrary<Toast> = fc.record({
  id: fc.uuid().map((id) => `toast-${id}`),
  type: fc.constant('error' as ToastType),
  message: errorMessageArbitrary,
  duration: fc.option(fc.nat({ max: 10000 }), { nil: undefined }),
});

// Generator for failed document with error message
const failedDocumentArbitrary: fc.Arbitrary<Document> = fc.record({
  id: fc.uuid(),
  name: fc
    .string({ minLength: 3, maxLength: 50 })
    .filter((s) => s.trim().length >= 3)
    .map((s) => `FailedDoc_${s}`),
  status: fc.constant('failed' as DocumentStatus),
  errorMessage: errorMessageArbitrary,
  createdAt: fc
    .integer({ min: 1577836800000, max: 1924991999999 })
    .map((timestamp) => new Date(timestamp).toISOString()),
  pageCount: fc.option(fc.nat({ max: 1000 }), { nil: undefined }),
});

/**
 * Wrapper component for testing
 */
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

/**
 * Simple Toast Display Component for testing
 */
function ToastDisplay() {
  const { toasts } = useUIStore();

  return (
    <div data-testid="toast-container">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          data-testid={`toast-${toast.type}`}
          className={`toast toast-${toast.type}`}
          role="alert"
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}

describe('Error Message Display Property Tests', () => {
  beforeEach(() => {
    // Reset store states before each test
    useUIStore.setState({
      theme: 'light',
      isLoading: false,
      toasts: [],
    });
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: false,
    });
  });

  afterEach(() => {
    cleanup();
    // Reset store states after each test
    useUIStore.setState({
      theme: 'light',
      isLoading: false,
      toasts: [],
    });
    useDocumentStore.setState({
      documents: [],
      selectedDocumentId: null,
      uploadProgress: new Map(),
      isLoading: false,
    });
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 5.3**
   *
   * For any error toast, the UI should display the error message.
   */
  it('displays error toast messages correctly', () => {
    fc.assert(
      fc.property(errorToastArbitrary, (toast: Toast) => {
        // Clean up any previous renders
        cleanup();

        // Add toast to store
        useUIStore.setState({
          toasts: [toast],
        });

        // Render the toast display component
        const { container, unmount } = render(
          <TestWrapper>
            <ToastDisplay />
          </TestWrapper>
        );

        // Verify toast container exists
        const toastContainer = container.querySelector('[data-testid="toast-container"]');
        expect(toastContainer).not.toBeNull();

        // Verify error toast is rendered with correct message
        const errorToast = container.querySelector('[data-testid="toast-error"]');
        expect(errorToast).not.toBeNull();
        expect(errorToast?.textContent).toContain(toast.message);

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 5.3**
   *
   * For any list of toasts, all toast messages should be displayed.
   */
  it('displays all toast messages in the list', () => {
    fc.assert(
      fc.property(
        fc.array(toastArbitrary, { minLength: 1, maxLength: 5 }).map((toasts) =>
          toasts.map((t, i) => ({ ...t, id: `toast-${i}-${t.id}` }))
        ),
        (toasts: Toast[]) => {
          // Clean up any previous renders
          cleanup();

          // Add toasts to store
          useUIStore.setState({ toasts });

          // Render the toast display component
          const { container, unmount } = render(
            <TestWrapper>
              <ToastDisplay />
            </TestWrapper>
          );

          // Verify all toast messages are rendered
          for (const toast of toasts) {
            expect(container.textContent).toContain(toast.message);
          }

          // Clean up
          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 2.6**
   *
   * For any failed document, the error message should be displayed in the document list.
   */
  it('displays error message for failed documents in document list', () => {
    fc.assert(
      fc.property(
        fc.array(failedDocumentArbitrary, { minLength: 1, maxLength: 3 }).map((docs) =>
          docs.map((d, i) => ({ ...d, id: `failed-${i}-${d.id}` }))
        ),
        (documents: Document[]) => {
          // Clean up any previous renders
          cleanup();

          // Set up store with failed documents
          useDocumentStore.setState({
            documents,
            selectedDocumentId: null,
            uploadProgress: new Map(),
            isLoading: false,
          });

          // Render the document list
          const { container, unmount } = render(
            <TestWrapper>
              <DocumentList />
            </TestWrapper>
          );

          // Verify each failed document's error message is displayed
          for (const doc of documents) {
            if (doc.errorMessage) {
              expect(container.textContent).toContain(doc.errorMessage);
            }
          }

          // Clean up
          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 5.3**
   *
   * The showToast action should add a toast with the correct type and message.
   */
  it('showToast adds toast with correct type and message', () => {
    fc.assert(
      fc.property(
        toastTypeArbitrary,
        errorMessageArbitrary,
        (type: ToastType, message: string) => {
          // Reset store
          useUIStore.setState({ toasts: [] });

          // Call showToast
          useUIStore.getState().showToast(type, message);

          // Verify toast was added
          const { toasts } = useUIStore.getState();
          expect(toasts.length).toBe(1);
          expect(toasts[0].type).toBe(type);
          expect(toasts[0].message).toBe(message);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 5.3**
   *
   * Multiple showToast calls should accumulate toasts.
   */
  it('multiple showToast calls accumulate toasts', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.tuple(toastTypeArbitrary, errorMessageArbitrary),
          { minLength: 1, maxLength: 5 }
        ),
        (toastData: [ToastType, string][]) => {
          // Reset store
          useUIStore.setState({ toasts: [] });

          // Call showToast for each toast
          for (const [type, message] of toastData) {
            useUIStore.getState().showToast(type, message, 0); // duration 0 to prevent auto-dismiss
          }

          // Verify all toasts were added
          const { toasts } = useUIStore.getState();
          expect(toasts.length).toBe(toastData.length);

          // Verify each toast has correct type and message
          for (let i = 0; i < toastData.length; i++) {
            expect(toasts[i].type).toBe(toastData[i][0]);
            expect(toasts[i].message).toBe(toastData[i][1]);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 3: Error message display**
   * **Validates: Requirements 5.3**
   *
   * dismissToast should remove the specified toast.
   */
  it('dismissToast removes the specified toast', () => {
    fc.assert(
      fc.property(
        fc.array(toastArbitrary, { minLength: 2, maxLength: 5 }).map((toasts) =>
          toasts.map((t, i) => ({ ...t, id: `toast-${i}-${t.id}` }))
        ),
        fc.nat(),
        (toasts: Toast[], indexToRemove: number) => {
          // Set up store with toasts
          useUIStore.setState({ toasts });

          // Pick a toast to remove
          const targetIndex = indexToRemove % toasts.length;
          const toastToRemove = toasts[targetIndex];

          // Dismiss the toast
          useUIStore.getState().dismissToast(toastToRemove.id);

          // Verify toast was removed
          const { toasts: remainingToasts } = useUIStore.getState();
          expect(remainingToasts.length).toBe(toasts.length - 1);
          expect(remainingToasts.find((t) => t.id === toastToRemove.id)).toBeUndefined();

          // Verify other toasts are still present
          for (const toast of toasts) {
            if (toast.id !== toastToRemove.id) {
              expect(remainingToasts.find((t) => t.id === toast.id)).toBeDefined();
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
