/**
 * Subscription Page - Display subscription status, features, and credits
 * Requirements: 4.1, 4.2, 4.4
 */

import { useState, useEffect, useCallback } from 'react';
import { useUIStore } from '../stores/uiStore';
import { apiClient } from '../services/apiClient';
import { ApiKeysManager } from '../components';
import type { Subscription, SubscriptionPlan } from '../types';

/**
 * Plan configuration with display info
 */
const PLAN_CONFIG: Record<SubscriptionPlan, { name: string; description: string; color: string }> = {
  free: {
    name: 'Free',
    description: 'Basic access to document analysis',
    color: 'text-gray-600 dark:text-gray-400',
  },
  pro: {
    name: 'Pro',
    description: 'Advanced features for power users',
    color: 'text-primary-600 dark:text-primary-400',
  },
  enterprise: {
    name: 'Enterprise',
    description: 'Full access with priority support',
    color: 'text-purple-600 dark:text-purple-400',
  },
};

/**
 * Credit usage progress bar component
 */
interface CreditProgressProps {
  remaining: number;
  total: number;
}

function CreditProgress({ remaining, total }: CreditProgressProps) {
  const percentage = total > 0 ? Math.round((remaining / total) * 100) : 0;
  const isLow = percentage < 20;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-[var(--text-secondary)]">Credits Remaining</span>
        <span className={`font-medium ${isLow ? 'text-error-500' : 'text-[var(--text-primary)]'}`}>
          {remaining.toLocaleString()} / {total.toLocaleString()}
        </span>
      </div>
      <div className="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${isLow ? 'bg-error-500' : 'bg-primary-500'
            }`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={remaining}
          aria-valuemin={0}
          aria-valuemax={total}
        />
      </div>
      {isLow && (
        <p className="text-xs text-error-500">
          Your credits are running low. Consider upgrading your plan.
        </p>
      )}
    </div>
  );
}

/**
 * Feature list component
 */
interface FeatureListProps {
  features: string[];
}

function FeatureList({ features }: FeatureListProps) {
  if (features.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">No features available</p>
    );
  }

  return (
    <ul className="space-y-2">
      {features.map((feature, index) => (
        <li key={index} className="flex items-start gap-2">
          <svg
            className="w-5 h-5 text-success-500 flex-shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span className="text-sm text-[var(--text-secondary)]">{feature}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Skeleton loader for subscription data
 */
function SubscriptionSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-8 bg-[var(--bg-tertiary)] rounded w-1/3" />
      <div className="h-4 bg-[var(--bg-tertiary)] rounded w-1/2" />
      <div className="space-y-3">
        <div className="h-4 bg-[var(--bg-tertiary)] rounded w-full" />
        <div className="h-2 bg-[var(--bg-tertiary)] rounded w-full" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-4 bg-[var(--bg-tertiary)] rounded w-3/4" />
        ))}
      </div>
    </div>
  );
}

export function Subscription() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const { showToast } = useUIStore();

  /**
   * Fetch subscription data on mount
   */
  useEffect(() => {
    const fetchSubscription = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get<Subscription>('/subscription');
        setSubscription(response);
      } catch {
        showToast('error', 'Failed to load subscription data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSubscription();
  }, [showToast]);

  /**
   * Handle upgrade button click
   */
  const handleUpgrade = useCallback(async () => {
    setIsUpgrading(true);
    try {
      const response = await apiClient.post<{ checkoutUrl: string }>('/subscription/checkout');
      // Redirect to checkout URL
      window.location.href = response.checkoutUrl;
    } catch {
      showToast('error', 'Failed to initiate checkout');
      setIsUpgrading(false);
    }
  }, [showToast]);

  const planConfig = subscription ? PLAN_CONFIG[subscription.plan] : null;
  const canUpgrade = subscription && subscription.plan !== 'enterprise';

  return (
    <div className="h-full overflow-auto bg-[var(--bg-primary)]">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-2">
            Subscription
          </h1>
          <p className="text-[var(--text-secondary)]">
            Manage your subscription plan and credits
          </p>
        </div>

        {/* Subscription Card */}
        <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] p-6 mb-6">
          {isLoading ? (
            <SubscriptionSkeleton />
          ) : subscription ? (
            <div className="space-y-6">
              {/* Plan Info */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                    Current Plan
                  </h2>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${planConfig?.color} bg-[var(--bg-tertiary)]`}
                    data-testid="plan-badge"
                  >
                    {planConfig?.name}
                  </span>
                </div>
                <p className="text-sm text-[var(--text-secondary)]">
                  {planConfig?.description}
                </p>
              </div>

              {/* Credits */}
              <CreditProgress
                remaining={subscription.remainingCredits}
                total={subscription.totalCredits}
              />

              {/* Features */}
              <div>
                <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
                  Included Features
                </h3>
                <FeatureList features={subscription.features} />
              </div>

              {/* Upgrade Button */}
              {canUpgrade && (
                <button
                  onClick={handleUpgrade}
                  disabled={isUpgrading}
                  className="w-full px-4 py-3 rounded-lg bg-primary-500 text-white font-medium hover:bg-primary-600 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  data-testid="upgrade-button"
                >
                  {isUpgrading ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                        />
                      </svg>
                      <span>Upgrade Plan</span>
                    </>
                  )}
                </button>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-[var(--text-secondary)]">
                Unable to load subscription data
              </p>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 px-4 py-2 text-sm text-primary-500 hover:text-primary-600"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* API Keys Section - Only show for plans with API access */}
        {subscription && (subscription.plan === 'pro' || subscription.plan === 'enterprise') && (
          <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] p-6 mb-6">
            <ApiKeysManager />
          </div>
        )}

        {/* Help Section */}
        <div className="bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)] p-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
            Need Help?
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Have questions about your subscription or need assistance? Our support team is here to help.
          </p>
          <a
            href="mailto:support@example.com"
            className="inline-flex items-center gap-2 text-sm text-primary-500 hover:text-primary-600"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
            Contact Support
          </a>
        </div>
      </div>
    </div>
  );
}

export default Subscription;
