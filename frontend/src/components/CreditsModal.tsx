/**
 * Credits Insufficient Modal - Displays when user runs out of credits
 * Requirements: 4.3
 */

import { useCallback } from 'react';
import { apiClient } from '../services/apiClient';
import { useUIStore } from '../stores/uiStore';

export interface CreditsModalProps {
  isOpen: boolean;
  remainingCredits: number;
  onClose: () => void;
  onUpgradeSuccess?: () => void;
}

/**
 * Upgrade plan options
 */
const UPGRADE_OPTIONS = [
  {
    plan: 'pro',
    name: 'Pro Plan',
    price: '$19/month',
    credits: '5,000 credits/month',
    features: ['Priority support', 'Advanced analytics', 'API access'],
  },
  {
    plan: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    credits: 'Unlimited credits',
    features: ['Dedicated support', 'Custom integrations', 'SLA guarantee'],
  },
];

export function CreditsModal({
  isOpen,
  remainingCredits,
  onClose,
  onUpgradeSuccess,
}: CreditsModalProps) {
  const { showToast } = useUIStore();

  const handleUpgrade = useCallback(
    async (plan: string) => {
      try {
        const response = await apiClient.post<{ checkoutUrl: string }>(
          '/subscription/checkout',
          { plan }
        );
        // Redirect to checkout URL
        window.location.href = response.checkoutUrl;
        onUpgradeSuccess?.();
      } catch {
        showToast('error', 'Failed to initiate checkout. Please try again.');
      }
    },
    [showToast, onUpgradeSuccess]
  );

  const handleContactSales = useCallback(() => {
    window.open('mailto:sales@example.com?subject=Enterprise%20Plan%20Inquiry', '_blank');
  }, []);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="credits-modal-title"
      data-testid="credits-modal"
    >
      <div
        className="bg-[var(--bg-secondary)] rounded-xl shadow-xl max-w-lg w-full p-6 border border-[var(--border-color)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Warning Icon */}
        <div className="mx-auto w-14 h-14 rounded-full bg-warning-100 dark:bg-warning-900/30 flex items-center justify-center mb-4">
          <svg
            className="w-7 h-7 text-warning-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Title */}
        <h2
          id="credits-modal-title"
          className="text-xl font-semibold text-[var(--text-primary)] text-center mb-2"
        >
          Credits Running Low
        </h2>

        {/* Message */}
        <p className="text-sm text-[var(--text-secondary)] text-center mb-2">
          You have{' '}
          <span className="font-semibold text-warning-500">
            {remainingCredits.toLocaleString()}
          </span>{' '}
          credits remaining.
        </p>
        <p className="text-sm text-[var(--text-muted)] text-center mb-6">
          Upgrade your plan to continue using all features without interruption.
        </p>

        {/* Upgrade Options */}
        <div className="space-y-3 mb-6">
          {UPGRADE_OPTIONS.map((option) => (
            <div
              key={option.plan}
              className="p-4 rounded-lg border border-[var(--border-color)] hover:border-primary-500 transition-colors duration-200"
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="font-medium text-[var(--text-primary)]">
                    {option.name}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">{option.credits}</p>
                </div>
                <span className="text-lg font-semibold text-primary-500">
                  {option.price}
                </span>
              </div>
              <ul className="text-xs text-[var(--text-secondary)] space-y-1 mb-3">
                {option.features.map((feature, index) => (
                  <li key={index} className="flex items-center gap-1">
                    <svg
                      className="w-3 h-3 text-success-500"
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
                    {feature}
                  </li>
                ))}
              </ul>
              {option.plan === 'enterprise' ? (
                <button
                  onClick={handleContactSales}
                  className="w-full px-3 py-2 rounded-lg border border-primary-500 text-primary-500 text-sm font-medium hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors duration-200"
                  data-testid={`contact-sales-${option.plan}`}
                >
                  Contact Sales
                </button>
              ) : (
                <button
                  onClick={() => handleUpgrade(option.plan)}
                  className="w-full px-3 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors duration-200"
                  data-testid={`upgrade-${option.plan}`}
                >
                  Upgrade to {option.name}
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="w-full px-4 py-2.5 rounded-lg border border-[var(--border-color)] text-[var(--text-secondary)] font-medium hover:bg-[var(--bg-tertiary)] transition-colors duration-200"
          data-testid="credits-modal-close"
        >
          Maybe Later
        </button>
      </div>
    </div>
  );
}

export default CreditsModal;
