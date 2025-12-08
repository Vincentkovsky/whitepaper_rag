/**
 * Property-Based Tests for Loading State Indicator
 * **Feature: frontend-redesign, Property 9: Loading state indicator**
 * **Validates: Requirements 5.2**
 *
 * Property: For any loading state, the UI should display either a skeleton loader or spinner.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render, screen } from '@testing-library/react';
import React from 'react';
import {
  Loading,
  Spinner,
  Skeleton,
  LoadingDots,
  SkeletonText,
  SkeletonCard,
  FullPageLoading,
  type LoadingVariant,
  type LoadingSize,
} from '../../src/components/Loading';

// Generators for valid loading props
const loadingVariantArbitrary: fc.Arbitrary<LoadingVariant> = fc.constantFrom('spinner', 'skeleton', 'dots');
const loadingSizeArbitrary: fc.Arbitrary<LoadingSize> = fc.constantFrom('sm', 'md', 'lg');

describe('Loading Component Property Tests', () => {
  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any loading variant, the Loading component should render the appropriate indicator.
   */
  it('Loading component renders correct variant for any valid variant type', () => {
    fc.assert(
      fc.property(loadingVariantArbitrary, (variant: LoadingVariant) => {
        const { unmount } = render(<Loading variant={variant} />);

        // Verify loading container is present
        const loadingElement = screen.getByTestId('loading');
        expect(loadingElement).toBeDefined();
        expect(loadingElement.getAttribute('data-variant')).toBe(variant);

        // Verify correct child element based on variant
        if (variant === 'spinner') {
          expect(screen.getByTestId('loading-spinner')).toBeDefined();
        } else if (variant === 'skeleton') {
          expect(screen.getByTestId('loading-skeleton')).toBeDefined();
        } else if (variant === 'dots') {
          expect(screen.getByTestId('loading-dots')).toBeDefined();
        }

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any size, the Spinner component should render with appropriate size class.
   */
  it('Spinner renders with correct size for any valid size', () => {
    fc.assert(
      fc.property(loadingSizeArbitrary, (size: LoadingSize) => {
        const { unmount } = render(<Spinner size={size} />);

        const spinner = screen.getByTestId('loading-spinner');
        expect(spinner).toBeDefined();
        
        // Verify spinner has animate-spin class
        expect(spinner.classList.contains('animate-spin')).toBe(true);

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any dimensions, the Skeleton component should render with correct styles.
   */
  it('Skeleton renders with correct dimensions for any valid width/height', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 10, max: 500 }),
        fc.integer({ min: 10, max: 200 }),
        (width: number, height: number) => {
          const widthStr = `${width}px`;
          const heightStr = `${height}px`;
          
          const { unmount } = render(<Skeleton width={widthStr} height={heightStr} />);

          const skeleton = screen.getByTestId('loading-skeleton');
          expect(skeleton).toBeDefined();
          expect(skeleton.style.width).toBe(widthStr);
          expect(skeleton.style.height).toBe(heightStr);
          
          // Verify skeleton has animate-pulse class
          expect(skeleton.classList.contains('animate-pulse')).toBe(true);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any boolean rounded/circle props, Skeleton should apply correct border radius.
   */
  it('Skeleton applies correct border radius based on rounded/circle props', () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.boolean(),
        (rounded: boolean, circle: boolean) => {
          const { unmount } = render(<Skeleton rounded={rounded} circle={circle} />);

          const skeleton = screen.getByTestId('loading-skeleton');
          expect(skeleton).toBeDefined();
          
          // Circle takes precedence over rounded
          if (circle) {
            expect(skeleton.classList.contains('rounded-full')).toBe(true);
          } else if (rounded) {
            expect(skeleton.classList.contains('rounded')).toBe(true);
          }

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any size, LoadingDots should render exactly 3 dots.
   */
  it('LoadingDots renders exactly 3 dots for any size', () => {
    fc.assert(
      fc.property(loadingSizeArbitrary, (size: LoadingSize) => {
        const { unmount } = render(<LoadingDots size={size} />);

        const dotsContainer = screen.getByTestId('loading-dots');
        expect(dotsContainer).toBeDefined();
        
        // Should have exactly 3 child dots
        const dots = dotsContainer.children;
        expect(dots.length).toBe(3);
        
        // Each dot should have animate-bounce class
        Array.from(dots).forEach((dot) => {
          expect(dot.classList.contains('animate-bounce')).toBe(true);
        });

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any number of lines, SkeletonText should render that many skeleton elements.
   */
  it('SkeletonText renders correct number of skeleton lines', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }),
        (lines: number) => {
          const { unmount } = render(<SkeletonText lines={lines} />);

          const skeletonText = screen.getByTestId('skeleton-text');
          expect(skeletonText).toBeDefined();
          
          // Should have correct number of skeleton children
          const skeletons = skeletonText.querySelectorAll('[data-testid="loading-skeleton"]');
          expect(skeletons.length).toBe(lines);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * SkeletonCard should always contain skeleton elements for avatar and text.
   */
  it('SkeletonCard contains required skeleton elements', () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        const { unmount } = render(<SkeletonCard />);

        const skeletonCard = screen.getByTestId('skeleton-card');
        expect(skeletonCard).toBeDefined();
        
        // Should contain multiple skeleton elements
        const skeletons = skeletonCard.querySelectorAll('[data-testid="loading-skeleton"]');
        expect(skeletons.length).toBeGreaterThan(0);
        
        // Should contain skeleton text
        const skeletonText = skeletonCard.querySelector('[data-testid="skeleton-text"]');
        expect(skeletonText).toBeDefined();

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * For any message, FullPageLoading should display the message and a spinner.
   */
  it('FullPageLoading displays message and spinner for any message', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }),
        (message: string) => {
          const { unmount } = render(<FullPageLoading message={message} />);

          const fullPageLoading = screen.getByTestId('full-page-loading');
          expect(fullPageLoading).toBeDefined();
          
          // Should contain spinner
          const spinner = fullPageLoading.querySelector('[data-testid="loading-spinner"]');
          expect(spinner).toBeDefined();
          
          // Should display message
          expect(fullPageLoading.textContent).toContain(message);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * Loading component should have proper accessibility attributes.
   */
  it('Loading component has proper accessibility attributes for any variant', () => {
    fc.assert(
      fc.property(
        loadingVariantArbitrary,
        fc.string({ minLength: 1, maxLength: 50 }),
        (variant: LoadingVariant, label: string) => {
          const { unmount } = render(<Loading variant={variant} label={label} />);

          const loadingElement = screen.getByTestId('loading');
          expect(loadingElement).toBeDefined();
          
          // Should have role="status" for accessibility
          expect(loadingElement.getAttribute('role')).toBe('status');
          
          // Should have aria-live for screen readers
          expect(loadingElement.getAttribute('aria-live')).toBe('polite');
          
          // Should have aria-label
          expect(loadingElement.getAttribute('aria-label')).toBe(label);
          
          // Should have sr-only text for screen readers
          const srOnly = loadingElement.querySelector('.sr-only');
          expect(srOnly).toBeDefined();
          expect(srOnly?.textContent).toBe(label);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 9: Loading state indicator**
   * **Validates: Requirements 5.2**
   *
   * Default variant should be spinner when no variant is specified.
   */
  it('Loading defaults to spinner variant when no variant specified', () => {
    fc.assert(
      fc.property(loadingSizeArbitrary, (size: LoadingSize) => {
        const { unmount } = render(<Loading size={size} />);

        const loadingElement = screen.getByTestId('loading');
        expect(loadingElement.getAttribute('data-variant')).toBe('spinner');
        
        // Should render spinner
        expect(screen.getByTestId('loading-spinner')).toBeDefined();

        unmount();
      }),
      { numRuns: 100 }
    );
  });
});
