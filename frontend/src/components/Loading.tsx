/**
 * Loading Component
 * Provides skeleton loaders and spinners for loading states
 * Requirements: 5.2
 */

import React from 'react';

export type LoadingVariant = 'spinner' | 'skeleton' | 'dots';
export type LoadingSize = 'sm' | 'md' | 'lg';

export interface LoadingProps {
  /** Loading variant type */
  variant?: LoadingVariant;
  /** Size of the loading indicator */
  size?: LoadingSize;
  /** Additional CSS class names */
  className?: string;
  /** Accessible label for screen readers */
  label?: string;
}

export interface SkeletonProps {
  /** Width of the skeleton (CSS value) */
  width?: string;
  /** Height of the skeleton (CSS value) */
  height?: string;
  /** Whether to use rounded corners */
  rounded?: boolean;
  /** Whether to use circular shape */
  circle?: boolean;
  /** Additional CSS class names */
  className?: string;
}

/**
 * Size configurations for spinner and dots
 */
const sizeConfig: Record<LoadingSize, { spinner: string; dots: string }> = {
  sm: { spinner: 'w-4 h-4', dots: 'w-1.5 h-1.5' },
  md: { spinner: 'w-8 h-8', dots: 'w-2 h-2' },
  lg: { spinner: 'w-12 h-12', dots: 'w-3 h-3' },
};

/**
 * Spinner Component - Animated circular spinner
 */
export const Spinner: React.FC<{ size?: LoadingSize; className?: string }> = ({
  size = 'md',
  className = '',
}) => {
  const sizeClass = sizeConfig[size].spinner;
  
  return (
    <svg
      className={`animate-spin text-blue-600 dark:text-blue-400 ${sizeClass} ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      data-testid="loading-spinner"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
};

/**
 * Skeleton Component - Placeholder loading animation
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '1rem',
  rounded = true,
  circle = false,
  className = '',
}) => {
  const roundedClass = circle ? 'rounded-full' : rounded ? 'rounded' : '';
  
  return (
    <div
      className={`animate-pulse bg-gray-200 dark:bg-gray-700 ${roundedClass} ${className}`}
      style={{ width, height }}
      data-testid="loading-skeleton"
      role="presentation"
      aria-hidden="true"
    />
  );
};

/**
 * Dots Component - Animated bouncing dots
 */
export const LoadingDots: React.FC<{ size?: LoadingSize; className?: string }> = ({
  size = 'md',
  className = '',
}) => {
  const dotSize = sizeConfig[size].dots;
  
  return (
    <div className={`flex items-center gap-1 ${className}`} data-testid="loading-dots">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className={`${dotSize} bg-blue-600 dark:bg-blue-400 rounded-full animate-bounce`}
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
};

/**
 * Loading Component - Main loading indicator with multiple variants
 */
export const Loading: React.FC<LoadingProps> = ({
  variant = 'spinner',
  size = 'md',
  className = '',
  label = 'Loading...',
}) => {
  const renderLoading = () => {
    switch (variant) {
      case 'spinner':
        return <Spinner size={size} />;
      case 'skeleton':
        return <Skeleton className="w-full h-4" />;
      case 'dots':
        return <LoadingDots size={size} />;
      default:
        return <Spinner size={size} />;
    }
  };

  return (
    <div
      className={`flex items-center justify-center ${className}`}
      role="status"
      aria-live="polite"
      aria-label={label}
      data-testid="loading"
      data-variant={variant}
    >
      {renderLoading()}
      <span className="sr-only">{label}</span>
    </div>
  );
};

/**
 * SkeletonText - Multiple skeleton lines for text content
 */
export const SkeletonText: React.FC<{
  lines?: number;
  className?: string;
}> = ({ lines = 3, className = '' }) => {
  return (
    <div className={`space-y-2 ${className}`} data-testid="skeleton-text">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          width={i === lines - 1 ? '75%' : '100%'}
          height="0.875rem"
        />
      ))}
    </div>
  );
};

/**
 * SkeletonCard - Skeleton placeholder for card content
 */
export const SkeletonCard: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div
      className={`p-4 border border-gray-200 dark:border-gray-700 rounded-lg ${className}`}
      data-testid="skeleton-card"
    >
      <div className="flex items-center gap-3 mb-4">
        <Skeleton width="2.5rem" height="2.5rem" circle />
        <div className="flex-1">
          <Skeleton width="60%" height="1rem" className="mb-2" />
          <Skeleton width="40%" height="0.75rem" />
        </div>
      </div>
      <SkeletonText lines={3} />
    </div>
  );
};

/**
 * FullPageLoading - Full page loading overlay
 */
export const FullPageLoading: React.FC<{ message?: string }> = ({
  message = 'Loading...',
}) => {
  return (
    <div
      className="fixed inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm z-50"
      data-testid="full-page-loading"
    >
      <Spinner size="lg" />
      <p className="mt-4 text-gray-600 dark:text-gray-400 text-sm">{message}</p>
    </div>
  );
};

export default Loading;
