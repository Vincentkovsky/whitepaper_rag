/**
 * Property-Based Tests for Theme Switching
 * **Feature: frontend-redesign, Property 10: Theme switching**
 * **Validates: Requirements 5.4**
 *
 * Property: For any theme value ('light' or 'dark'), setting the theme should
 * update the UI accordingly and persist the preference.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import { useUIStore, type Theme } from '../../src/stores/uiStore';
import { storageService } from '../../src/services/storageService';

// Generator for valid theme values
const themeArbitrary: fc.Arbitrary<Theme> = fc.constantFrom('light', 'dark');

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => Object.keys(store)[index] || null),
  };
})();

// Mock document.documentElement for dark mode class toggling
const mockClassList = {
  add: vi.fn(),
  remove: vi.fn(),
  toggle: vi.fn(),
  contains: vi.fn(),
};

describe('Theme Store Property Tests', () => {
  beforeEach(() => {
    // Reset store state before each test
    useUIStore.setState({
      theme: 'light',
      isLoading: false,
      toasts: [],
    });

    // Setup localStorage mock
    Object.defineProperty(global, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });
    localStorageMock.clear();

    // Setup document mock
    Object.defineProperty(global, 'document', {
      value: {
        documentElement: {
          classList: mockClassList,
        },
      },
      writable: true,
    });

    // Clear mock call history
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * For any valid theme value, setTheme should update the store state correctly.
   */
  it('setTheme updates store state for any valid theme', () => {
    fc.assert(
      fc.property(themeArbitrary, (theme: Theme) => {
        // Reset state
        useUIStore.setState({
          theme: theme === 'light' ? 'dark' : 'light', // Start with opposite theme
          isLoading: false,
          toasts: [],
        });

        // Set theme
        useUIStore.getState().setTheme(theme);

        // Verify state
        const state = useUIStore.getState();
        expect(state.theme).toBe(theme);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * For any theme, toggleTheme should switch to the opposite theme.
   */
  it('toggleTheme switches between light and dark', () => {
    fc.assert(
      fc.property(themeArbitrary, (initialTheme: Theme) => {
        // Reset state with initial theme
        useUIStore.setState({
          theme: initialTheme,
          isLoading: false,
          toasts: [],
        });

        // Toggle theme
        useUIStore.getState().toggleTheme();

        // Verify state switched to opposite
        const state = useUIStore.getState();
        const expectedTheme = initialTheme === 'light' ? 'dark' : 'light';
        expect(state.theme).toBe(expectedTheme);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * Double toggle should return to original theme (involution property).
   */
  it('double toggleTheme returns to original theme', () => {
    fc.assert(
      fc.property(themeArbitrary, (initialTheme: Theme) => {
        // Reset state with initial theme
        useUIStore.setState({
          theme: initialTheme,
          isLoading: false,
          toasts: [],
        });

        // Toggle twice
        useUIStore.getState().toggleTheme();
        useUIStore.getState().toggleTheme();

        // Verify state returned to original
        const state = useUIStore.getState();
        expect(state.theme).toBe(initialTheme);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * setTheme should apply dark class to document when theme is 'dark'.
   */
  it('setTheme applies correct CSS class to document', () => {
    fc.assert(
      fc.property(themeArbitrary, (theme: Theme) => {
        // Reset mocks
        vi.clearAllMocks();

        // Reset state
        useUIStore.setState({
          theme: theme === 'light' ? 'dark' : 'light',
          isLoading: false,
          toasts: [],
        });

        // Set theme
        useUIStore.getState().setTheme(theme);

        // Verify classList.toggle was called with correct arguments
        expect(mockClassList.toggle).toHaveBeenCalledWith('dark', theme === 'dark');
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * Theme persistence: saveTheme then loadTheme should return the same theme.
   */
  it('theme persistence round-trip preserves theme value', () => {
    fc.assert(
      fc.property(themeArbitrary, (theme: Theme) => {
        // Save theme
        storageService.saveTheme(theme);

        // Load theme
        const loadedTheme = storageService.loadTheme();

        // Verify round-trip
        expect(loadedTheme).toBe(theme);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * Setting theme multiple times should always result in the last set value.
   */
  it('multiple setTheme calls result in last value', () => {
    fc.assert(
      fc.property(
        fc.array(themeArbitrary, { minLength: 1, maxLength: 10 }),
        (themes: Theme[]) => {
          // Reset state
          useUIStore.setState({
            theme: 'light',
            isLoading: false,
            toasts: [],
          });

          // Set themes in sequence
          for (const theme of themes) {
            useUIStore.getState().setTheme(theme);
          }

          // Verify final state is last theme
          const state = useUIStore.getState();
          expect(state.theme).toBe(themes[themes.length - 1]);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 10: Theme switching**
   * **Validates: Requirements 5.4**
   *
   * Theme changes should not affect other UI state (loading, toasts).
   */
  it('setTheme does not affect other UI state', () => {
    fc.assert(
      fc.property(
        themeArbitrary,
        fc.boolean(),
        fc.array(fc.record({
          id: fc.uuid(),
          type: fc.constantFrom('success', 'error', 'warning', 'info'),
          message: fc.string({ minLength: 1, maxLength: 100 }),
          duration: fc.option(fc.nat({ max: 10000 }), { nil: undefined }),
        }), { minLength: 0, maxLength: 5 }),
        (theme, isLoading, toasts) => {
          // Set up initial state with various values
          useUIStore.setState({
            theme: theme === 'light' ? 'dark' : 'light',
            isLoading,
            toasts: toasts as any[],
          });

          // Store original values
          const originalLoading = isLoading;
          const originalToasts = [...toasts];

          // Change theme
          useUIStore.getState().setTheme(theme);

          // Verify other state unchanged
          const state = useUIStore.getState();
          expect(state.isLoading).toBe(originalLoading);
          expect(state.toasts).toEqual(originalToasts);
        }
      ),
      { numRuns: 100 }
    );
  });
});
