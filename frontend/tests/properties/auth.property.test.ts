/**
 * Property-Based Tests for Auth Store
 * **Feature: frontend-redesign, Property 1: Authentication state consistency**
 * **Validates: Requirements 1.3, 1.4**
 *
 * Property: For any authentication action (login success, logout), the auth state
 * should transition correctly: login sets user and token, logout clears both.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { useAuthStore } from '../../src/stores/authStore';
import type { User } from '../../src/types';

// Generator for valid User objects
const userArbitrary = fc.record({
  id: fc.uuid(),
  email: fc.emailAddress(),
  name: fc.option(fc.string({ minLength: 1, maxLength: 100 }), { nil: undefined }),
  avatarUrl: fc.option(fc.webUrl(), { nil: undefined }),
});

// Generator for valid access tokens (non-empty strings)
const accessTokenArbitrary = fc.string({ minLength: 1, maxLength: 500 });

describe('Auth Store Property Tests', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isLoading: false,
    });
  });

  /**
   * **Feature: frontend-redesign, Property 1: Authentication state consistency**
   * **Validates: Requirements 1.3, 1.4**
   *
   * For any valid user and access token, login should set both user and token,
   * and isAuthenticated should be true.
   */
  it('login sets user and token correctly for any valid input', () => {
    fc.assert(
      fc.property(userArbitrary, accessTokenArbitrary, (user: User, token: string) => {
        // Reset state
        useAuthStore.setState({
          user: null,
          accessToken: null,
          isLoading: false,
        });

        // Perform login
        useAuthStore.getState().login(user, token);

        // Verify state
        const state = useAuthStore.getState();
        expect(state.user).toEqual(user);
        expect(state.accessToken).toBe(token);
        expect(state.isAuthenticated()).toBe(true);
        expect(state.isLoading).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 1: Authentication state consistency**
   * **Validates: Requirements 1.3, 1.4**
   *
   * For any authenticated state, logout should clear both user and token,
   * and isAuthenticated should be false.
   */
  it('logout clears user and token for any authenticated state', () => {
    fc.assert(
      fc.property(userArbitrary, accessTokenArbitrary, (user: User, token: string) => {
        // Set up authenticated state
        useAuthStore.setState({
          user,
          accessToken: token,
          isLoading: false,
        });

        // Perform logout
        useAuthStore.getState().logout();

        // Verify state
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
        expect(state.isAuthenticated()).toBe(false);
        expect(state.isLoading).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 1: Authentication state consistency**
   * **Validates: Requirements 1.3, 1.4**
   *
   * For any sequence of login followed by logout, the final state should be
   * unauthenticated with cleared user and token.
   */
  it('login then logout results in unauthenticated state', () => {
    fc.assert(
      fc.property(userArbitrary, accessTokenArbitrary, (user: User, token: string) => {
        // Reset state
        useAuthStore.setState({
          user: null,
          accessToken: null,
          isLoading: false,
        });

        // Login then logout
        useAuthStore.getState().login(user, token);
        useAuthStore.getState().logout();

        // Verify final state
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
        expect(state.isAuthenticated()).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * **Feature: frontend-redesign, Property 1: Authentication state consistency**
   * **Validates: Requirements 1.3, 1.4**
   *
   * isAuthenticated should be true if and only if both user and accessToken are non-null.
   */
  it('isAuthenticated is true iff user and token are both present', () => {
    fc.assert(
      fc.property(
        fc.option(userArbitrary, { nil: null }),
        fc.option(accessTokenArbitrary, { nil: null }),
        (user: User | null, token: string | null) => {
          // Set state directly
          useAuthStore.setState({
            user,
            accessToken: token,
            isLoading: false,
          });

          const state = useAuthStore.getState();
          const expectedAuth = user !== null && token !== null;
          expect(state.isAuthenticated()).toBe(expectedAuth);
        }
      ),
      { numRuns: 100 }
    );
  });
});
