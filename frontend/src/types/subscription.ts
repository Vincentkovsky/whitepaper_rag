/**
 * Subscription-related type definitions
 * Requirements: 7.1
 */

export type SubscriptionPlan = 'free' | 'pro' | 'enterprise';

export interface Subscription {
  plan: SubscriptionPlan;
  features: string[];
  remainingCredits: number;
  totalCredits: number;
}
