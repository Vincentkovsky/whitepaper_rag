/**
 * Auth Guard Component - Protects routes requiring authentication
 * Requirements: 1.1, 1.5
 */

import { useEffect, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/authService';

interface AuthGuardProps {
  children: ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const location = useLocation();
  const { isAuthenticated, isLoading, user, accessToken } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        await authService.initialize();
      } catch (error) {
        console.error('Failed to initialize auth:', error);
      } finally {
        setIsInitialized(true);
      }
    };

    if (!isInitialized) {
      initAuth();
    }
  }, [isInitialized]);

  // Handle token refresh when token might be expired
  useEffect(() => {
    const refreshTokenIfNeeded = async () => {
      // Only attempt refresh if we have a user but might need a fresh token
      if (user && accessToken && !isRefreshing) {
        try {
          setIsRefreshing(true);
          // Supabase handles token refresh automatically, but we can force it
          await authService.refreshSession();
        } catch (error) {
          console.error('Token refresh failed:', error);
          // If refresh fails, the user will be redirected to login
        } finally {
          setIsRefreshing(false);
        }
      }
    };

    // Set up periodic token refresh (every 10 minutes)
    const refreshInterval = setInterval(refreshTokenIfNeeded, 10 * 60 * 1000);

    return () => clearInterval(refreshInterval);
  }, [user, accessToken, isRefreshing]);

  // Show loading state while initializing
  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-[var(--text-secondary)]">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated()) {
    // Save the attempted URL for redirecting after login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Render protected content
  return <>{children}</>;
}

export default AuthGuard;
