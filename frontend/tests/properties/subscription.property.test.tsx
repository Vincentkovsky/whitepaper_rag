/**
 * Property-Based Tests for Subscription Display Completeness
 * **Feature: frontend-redesign, Property 8: Subscription display completeness**
 * **Validates: Requirements 4.1**
 *
 * Property: For any subscription data, the rendered output should contain
 * plan name, features list, and remaining credits.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fc from 'fast-check';
import { render, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Subscription } from '../../src/pages/Subscription';
import type { Subscription as SubscriptionType, SubscriptionPlan } from '../../src/types';

// Mock the apiClient
vi.mock('../../src/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

// Import the mocked module
import { apiClient } from '../../src/services/apiClient';

/**
 * Helper to mock API responses for subscription and api-keys
 */
function mockApiResponses(subscription: SubscriptionType) {
  vi.mocked(apiClient.get).mockImplementation((endpoint: string) => {
    if (endpoint === '/subscription') {
      return Promise.resolve(subscription);
    }
    if (endpoint === '/api-keys') {
      return Promise.resolve([]); // Return empty API keys list
    }
    return Promise.reject(new Error(`Unknown endpoint: ${endpoint}`));
  });
}

// Generator for SubscriptionPlan
const subscriptionPlanArbitrary: fc.Arbitrary<SubscriptionPlan> = fc.constantFrom(
  'free',
  'pro',
  'enterprise'
);

// Generator for feature strings
const featureArbitrary: fc.Arbitrary<string> = fc
  .string({ minLength: 3, maxLength: 50 })
  .filter((s) => s.trim().length >= 3 && /^[a-zA-Z]/.test(s));

// Generator for features array
const featuresArbitrary: fc.Arbitrary<string[]> = fc.array(featureArbitrary, {
  minLength: 1,
  maxLength: 5,
});

// Generator for Subscription
const subscriptionArbitrary: fc.Arbitrary<SubscriptionType> = fc.record({
  plan: subscriptionPlanArbitrary,
  features: featuresArbitrary,
  remainingCredits: fc.nat({ max: 10000 }),
  totalCredits: fc.nat({ max: 10000 }),
}).map((sub) => ({
  ...sub,
  // Ensure remainingCredits <= totalCredits
  remainingCredits: Math.min(sub.remainingCredits, sub.totalCredits),
  // Ensure totalCredits is at least 1 to avoid division by zero
  totalCredits: Math.max(sub.totalCredits, 1),
}));

/**
 * Get expected plan display name
 */
function getPlanDisplayName(plan: SubscriptionPlan): string {
  switch (plan) {
    case 'free':
      return 'Free';
    case 'pro':
      return 'Pro';
    case 'enterprise':
      return 'Enterprise';
    default:
      return plan;
  }
}

/**
 * Wrapper component for testing
 */
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

describe('Subscription Display Property Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * For any subscription data, the rendered output should contain
   * plan name, features list, and remaining credits.
   */
  it('renders plan name, features, and credits for any subscription', async () => {
    await fc.assert(
      fc.asyncProperty(subscriptionArbitrary, async (subscription: SubscriptionType) => {
        // Clean up any previous renders
        cleanup();
        vi.clearAllMocks();

        // Mock the API responses
        mockApiResponses(subscription);

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <Subscription />
          </TestWrapper>
        );

        // Wait for loading to complete
        await waitFor(() => {
          const skeleton = container.querySelector('.animate-pulse');
          expect(skeleton).toBeNull();
        }, { timeout: 2000 });

        // Check plan name is rendered
        const planName = getPlanDisplayName(subscription.plan);
        const planBadge = container.querySelector('[data-testid="plan-badge"]');
        expect(planBadge).not.toBeNull();
        expect(planBadge?.textContent).toContain(planName);

        // Check remaining credits is rendered
        const creditsText = subscription.remainingCredits.toLocaleString();
        expect(container.textContent).toContain(creditsText);

        // Check total credits is rendered
        const totalCreditsText = subscription.totalCredits.toLocaleString();
        expect(container.textContent).toContain(totalCreditsText);

        // Check each feature is rendered
        for (const feature of subscription.features) {
          expect(container.textContent).toContain(feature);
        }

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * The number of rendered feature items should match the number of features.
   */
  it('renders correct number of feature items', async () => {
    await fc.assert(
      fc.asyncProperty(subscriptionArbitrary, async (subscription: SubscriptionType) => {
        // Clean up any previous renders
        cleanup();
        vi.clearAllMocks();

        // Mock the API responses
        mockApiResponses(subscription);

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <Subscription />
          </TestWrapper>
        );

        // Wait for loading to complete
        await waitFor(() => {
          const skeleton = container.querySelector('.animate-pulse');
          expect(skeleton).toBeNull();
        }, { timeout: 2000 });

        // Count feature items (list items with checkmark icons)
        const featureItems = container.querySelectorAll('li');
        expect(featureItems.length).toBe(subscription.features.length);

        // Clean up
        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * Non-enterprise plans should show upgrade button.
   */
  it('shows upgrade button for non-enterprise plans', async () => {
    const nonEnterprisePlanArbitrary: fc.Arbitrary<SubscriptionPlan> = fc.constantFrom(
      'free',
      'pro'
    );

    const nonEnterpriseSubscriptionArbitrary: fc.Arbitrary<SubscriptionType> = fc.record({
      plan: nonEnterprisePlanArbitrary,
      features: featuresArbitrary,
      remainingCredits: fc.nat({ max: 10000 }),
      totalCredits: fc.nat({ max: 10000 }),
    }).map((sub) => ({
      ...sub,
      remainingCredits: Math.min(sub.remainingCredits, sub.totalCredits),
      totalCredits: Math.max(sub.totalCredits, 1),
    }));

    await fc.assert(
      fc.asyncProperty(nonEnterpriseSubscriptionArbitrary, async (subscription: SubscriptionType) => {
        // Clean up any previous renders
        cleanup();
        vi.clearAllMocks();

        // Mock the API responses
        mockApiResponses(subscription);

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <Subscription />
          </TestWrapper>
        );

        // Wait for loading to complete
        await waitFor(() => {
          const skeleton = container.querySelector('.animate-pulse');
          expect(skeleton).toBeNull();
        }, { timeout: 2000 });

        // Check upgrade button is present
        const upgradeButton = container.querySelector('[data-testid="upgrade-button"]');
        expect(upgradeButton).not.toBeNull();
        expect(upgradeButton?.textContent).toContain('Upgrade');

        // Clean up
        unmount();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * Enterprise plans should not show upgrade button.
   */
  it('hides upgrade button for enterprise plans', async () => {
    const enterpriseSubscriptionArbitrary: fc.Arbitrary<SubscriptionType> = fc.record({
      plan: fc.constant('enterprise' as SubscriptionPlan),
      features: featuresArbitrary,
      remainingCredits: fc.nat({ max: 10000 }),
      totalCredits: fc.nat({ max: 10000 }),
    }).map((sub) => ({
      ...sub,
      remainingCredits: Math.min(sub.remainingCredits, sub.totalCredits),
      totalCredits: Math.max(sub.totalCredits, 1),
    }));

    await fc.assert(
      fc.asyncProperty(enterpriseSubscriptionArbitrary, async (subscription: SubscriptionType) => {
        // Clean up any previous renders
        cleanup();
        vi.clearAllMocks();

        // Mock the API responses
        mockApiResponses(subscription);

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <Subscription />
          </TestWrapper>
        );

        // Wait for loading to complete
        await waitFor(() => {
          const skeleton = container.querySelector('.animate-pulse');
          expect(skeleton).toBeNull();
        }, { timeout: 2000 });

        // Check upgrade button is NOT present
        const upgradeButton = container.querySelector('[data-testid="upgrade-button"]');
        expect(upgradeButton).toBeNull();

        // Clean up
        unmount();
      }),
      { numRuns: 50 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * Loading state should show skeleton loaders.
   */
  it('renders skeleton loaders when loading', async () => {
    // Clean up any previous renders
    cleanup();
    vi.clearAllMocks();

    // Mock the API to never resolve (simulate loading)
    vi.mocked(apiClient.get).mockImplementation(() => new Promise(() => {}));

    // Render the component
    const { container, unmount } = render(
      <TestWrapper>
        <Subscription />
      </TestWrapper>
    );

    // Check for skeleton loaders (elements with animate-pulse class)
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);

    unmount();
  });

  /**
   * **Feature: frontend-redesign, Property 8: Subscription display completeness**
   * **Validates: Requirements 4.1**
   *
   * Low credits should show warning message.
   */
  it('shows warning when credits are low', async () => {
    // Generate subscription with low credits (< 20%)
    const lowCreditsSubscriptionArbitrary: fc.Arbitrary<SubscriptionType> = fc.record({
      plan: subscriptionPlanArbitrary,
      features: featuresArbitrary,
      totalCredits: fc.integer({ min: 100, max: 10000 }),
    }).map((sub) => ({
      ...sub,
      // Set remaining credits to less than 20% of total
      remainingCredits: Math.floor(sub.totalCredits * 0.1),
    }));

    await fc.assert(
      fc.asyncProperty(lowCreditsSubscriptionArbitrary, async (subscription: SubscriptionType) => {
        // Clean up any previous renders
        cleanup();
        vi.clearAllMocks();

        // Mock the API responses
        mockApiResponses(subscription);

        // Render the component
        const { container, unmount } = render(
          <TestWrapper>
            <Subscription />
          </TestWrapper>
        );

        // Wait for loading to complete
        await waitFor(() => {
          const skeleton = container.querySelector('.animate-pulse');
          expect(skeleton).toBeNull();
        }, { timeout: 2000 });

        // Check for low credits warning
        expect(container.textContent).toContain('credits are running low');

        // Clean up
        unmount();
      }),
      { numRuns: 50 }
    );
  });
});
