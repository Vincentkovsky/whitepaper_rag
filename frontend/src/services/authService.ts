/**
 * Auth Service - Supabase authentication integration
 * Requirements: 1.2, 1.3, 1.4
 */

import { createClient, type SupabaseClient, type Session, type User as SupabaseUser } from '@supabase/supabase-js';
import { useAuthStore } from '../stores/authStore';
import type { User } from '../types';

// Supabase client singleton
let supabaseClient: SupabaseClient | null = null;

/**
 * Get or create Supabase client
 */
const getSupabaseClient = (): SupabaseClient => {
  if (!supabaseClient) {
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
    const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseAnonKey) {
      throw new Error('Missing Supabase configuration. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.');
    }

    supabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  }
  return supabaseClient;
};

/**
 * Map Supabase user to app User type
 */
const mapSupabaseUser = (supabaseUser: SupabaseUser): User => ({
  id: supabaseUser.id,
  email: supabaseUser.email || '',
  name: supabaseUser.user_metadata?.full_name || supabaseUser.user_metadata?.name,
  avatarUrl: supabaseUser.user_metadata?.avatar_url || supabaseUser.user_metadata?.picture,
});

/**
 * Update auth store from session
 */
const updateAuthStore = (session: Session | null): void => {
  const { login, logout } = useAuthStore.getState();
  
  if (session?.user && session.access_token) {
    login(mapSupabaseUser(session.user), session.access_token);
  } else {
    logout();
  }
};


/**
 * Auth Service API
 */
export const authService = {
  /**
   * Initialize auth state and set up listeners
   */
  initialize: async (): Promise<void> => {
    const supabase = getSupabaseClient();
    const { setLoading } = useAuthStore.getState();
    
    setLoading(true);
    
    try {
      // Get current session
      const { data: { session } } = await supabase.auth.getSession();
      updateAuthStore(session);
      
      // Listen for auth state changes
      supabase.auth.onAuthStateChange((_event, session) => {
        updateAuthStore(session);
      });
    } finally {
      setLoading(false);
    }
  },

  /**
   * Sign in with Google OAuth
   * Requirements: 1.2
   */
  signInWithGoogle: async (): Promise<void> => {
    const supabase = getSupabaseClient();
    const { setLoading } = useAuthStore.getState();
    
    setLoading(true);
    
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      
      if (error) {
        throw error;
      }
    } finally {
      setLoading(false);
    }
  },

  /**
   * Sign out current user
   * Requirements: 1.4
   */
  signOut: async (): Promise<void> => {
    const supabase = getSupabaseClient();
    const { setLoading, logout } = useAuthStore.getState();
    
    setLoading(true);
    
    try {
      const { error } = await supabase.auth.signOut();
      
      if (error) {
        throw error;
      }
      
      logout();
    } finally {
      setLoading(false);
    }
  },

  /**
   * Get current session
   * Requirements: 1.3
   */
  getSession: async (): Promise<Session | null> => {
    const supabase = getSupabaseClient();
    const { data: { session } } = await supabase.auth.getSession();
    return session;
  },

  /**
   * Refresh the access token
   * Requirements: 1.5
   */
  refreshSession: async (): Promise<Session | null> => {
    const supabase = getSupabaseClient();
    const { refreshToken } = useAuthStore.getState();
    
    const { data: { session }, error } = await supabase.auth.refreshSession();
    
    if (error) {
      throw error;
    }
    
    if (session?.access_token) {
      refreshToken(session.access_token);
    }
    
    return session;
  },

  /**
   * Handle OAuth callback (for use in callback route)
   */
  handleCallback: async (): Promise<void> => {
    const supabase = getSupabaseClient();
    const { setLoading } = useAuthStore.getState();
    
    setLoading(true);
    
    try {
      // Supabase automatically handles the callback when detectSessionInUrl is true
      const { data: { session } } = await supabase.auth.getSession();
      updateAuthStore(session);
    } finally {
      setLoading(false);
    }
  },

  /**
   * Get the Supabase client (for advanced use cases)
   */
  getClient: (): SupabaseClient => getSupabaseClient(),
};

export default authService;
