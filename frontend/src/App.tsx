/**
 * App Component
 * Application entry point with routing and global providers
 * Requirements: 7.1
 */

import React, { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { useUIStore } from './stores/uiStore';
import { useAuthStore } from './stores/authStore';
import { authService } from './services/authService';

function App() {
  const { theme } = useUIStore();
  const { accessToken, user, login, logout } = useAuthStore();

  // Initialize theme on mount
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', theme === 'dark');
    }
  }, [theme]);

  // Restore user session if token exists but user is missing
  useEffect(() => {
    const restoreSession = async () => {
      if (accessToken && !user) {
        try {
          useAuthStore.getState().setLoading(true);
          // Ensure authService has the token (in case it was cleared from localStorage but exists in store)
          authService.setToken(accessToken);

          const userResponse = await authService.getCurrentUser();
          const mappedUser = {
            id: userResponse.id,
            email: userResponse.email,
            name: userResponse.name,
            avatarUrl: userResponse.avatar_url
          };
          login(mappedUser, accessToken);
        } catch (error) {
          console.error('Failed to restore session:', error);
          logout();
        } finally {
          useAuthStore.getState().setLoading(false);
        }
      }
    };

    restoreSession();
  }, [accessToken, user, login, logout]);

  return (
    <React.StrictMode>
      <RouterProvider router={router} />
    </React.StrictMode>
  );
}

export default App;
