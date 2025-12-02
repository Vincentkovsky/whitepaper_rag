/**
 * Auth Store - Manages authentication state
 * Requirements: 1.3, 1.4
 */

import { create } from 'zustand';
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

export const useAuthStore = create<AuthStore>((set, get) => ({
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
    set({
      user,
      accessToken,
      isLoading: false,
    });
  },

  logout: () => {
    set({
      user: null,
      accessToken: null,
      isLoading: false,
    });
  },

  refreshToken: (accessToken: string) => {
    set({ accessToken });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },
}));
