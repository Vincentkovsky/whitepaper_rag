/**
 * UI Store - Manages theme, loading states, and toast notifications
 * Requirements: 5.2, 5.4
 */

import { create } from 'zustand';

export type Theme = 'light' | 'dark';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface UIState {
  theme: Theme;
  isLoading: boolean;
  toasts: Toast[];
}

interface UIActions {
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setLoading: (isLoading: boolean) => void;
  showToast: (type: ToastType, message: string, duration?: number) => void;
  dismissToast: (id: string) => void;
  clearToasts: () => void;
}

type UIStore = UIState & UIActions;

// Generate unique ID for toasts
const generateId = () => `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export const useUIStore = create<UIStore>((set) => ({
  // State
  theme: 'light',
  isLoading: false,
  toasts: [],

  // Actions
  setTheme: (theme: Theme) => {
    set({ theme });
    // Apply theme to document for TailwindCSS dark mode
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', theme === 'dark');
    }
  },

  toggleTheme: () => {
    set(state => {
      const newTheme = state.theme === 'light' ? 'dark' : 'light';
      // Apply theme to document for TailwindCSS dark mode
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', newTheme === 'dark');
      }
      return { theme: newTheme };
    });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  showToast: (type: ToastType, message: string, duration = 5000) => {
    const id = generateId();
    set(state => ({
      toasts: [...state.toasts, { id, type, message, duration }],
    }));

    // Auto-dismiss toast after duration
    if (duration > 0) {
      setTimeout(() => {
        set(state => ({
          toasts: state.toasts.filter(t => t.id !== id),
        }));
      }, duration);
    }
  },

  dismissToast: (id: string) => {
    set(state => ({
      toasts: state.toasts.filter(t => t.id !== id),
    }));
  },

  clearToasts: () => {
    set({ toasts: [] });
  },
}));
