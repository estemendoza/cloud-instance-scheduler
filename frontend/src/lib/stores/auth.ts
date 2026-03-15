import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { apiClient } from '$lib/api/client';
import type { User, TokenResponse, RefreshResponse } from '$lib/types/user';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
}

const initialState: AuthState = {
  accessToken: null,
  refreshToken: browser ? localStorage.getItem('refreshToken') : null,
  user: null,
  isAuthenticated: false,
};

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>(initialState);

  return {
    subscribe,

    /**
     * Login with token response from /auth/token or /auth/bootstrap
     */
    login: (tokens: TokenResponse) => {
      if (browser) {
        localStorage.setItem('refreshToken', tokens.refresh_token);
      }

      update(state => ({
        ...state,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        user: tokens.user,
        isAuthenticated: true,
      }));

      apiClient.setAccessToken(tokens.access_token);
    },

    /**
     * Clear auth state and tokens
     */
    logout: () => {
      if (browser) {
        localStorage.removeItem('refreshToken');
      }

      set({
        accessToken: null,
        refreshToken: null,
        user: null,
        isAuthenticated: false,
      });

      apiClient.setAccessToken(null);
    },

    /**
     * Update user info
     */
    setUser: (user: User) => {
      update(state => ({
        ...state,
        user,
      }));
    },

    /**
     * Set a new access token (after refresh)
     */
    setAccessToken: (token: string) => {
      update(state => ({
        ...state,
        accessToken: token,
      }));
      apiClient.setAccessToken(token);
    },

    /**
     * Try to restore session from stored refresh token.
     * Returns true if session was restored, false otherwise.
     */
    restore: async (): Promise<boolean> => {
      if (!browser) return false;

      const refreshToken = localStorage.getItem('refreshToken');
      if (!refreshToken) return false;

      try {
        // Import here to avoid circular dependency
        const { authAPI } = await import('$lib/api/endpoints/auth');
        const { usersAPI } = await import('$lib/api/endpoints/users');

        // Get new access token
        const refreshResponse: RefreshResponse = await authAPI.refresh(refreshToken);
        apiClient.setAccessToken(refreshResponse.access_token);

        // Fetch user data
        const user = await usersAPI.me();

        // Update store
        update(state => ({
          ...state,
          accessToken: refreshResponse.access_token,
          refreshToken,
          user,
          isAuthenticated: true,
        }));

        return true;
      } catch {
        // Refresh failed, clear stored token
        localStorage.removeItem('refreshToken');
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        });
        apiClient.setAccessToken(null);
        return false;
      }
    },

    /**
     * Get current refresh token (for token refresh operations)
     */
    getRefreshToken: (): string | null => {
      return get({ subscribe }).refreshToken;
    },
  };
}

export const authStore = createAuthStore();
