/**
 * Auth Store - Manages authentication state
 * Requirements: 1.3, 1.4
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
}

interface AuthActions {
  login: (user: User, accessToken: string) => void;
  logout: () => void;
  refreshToken: (accessToken: string) => void;
  setLoading: (isLoading: boolean) => void;
  isAuthenticated: () => boolean;
}

type AuthStore = AuthState & AuthActions;

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      accessToken: null,
      isLoading: false,

      // Computed as function (Zustand doesn't support getters)
      isAuthenticated: () => {
        const state = get();
        return state.user !== null && state.accessToken !== null;
      },

      // Actions
      login: (user: User, accessToken: string) => {
        localStorage.setItem('auth_token', accessToken);
        set({
          user,
          accessToken,
          isLoading: false,
        });
      },

      logout: () => {
        localStorage.removeItem('auth_token');
        set({
          user: null,
          accessToken: null,
          isLoading: false,
        });
      },

      refreshToken: (accessToken: string) => {
        localStorage.setItem('auth_token', accessToken);
        set({ accessToken });
      },

      setLoading: (isLoading: boolean) => {
        set({ isLoading });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user
      }),
    }
  )
);
