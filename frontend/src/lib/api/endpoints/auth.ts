import { apiClient } from '../client';
import type {
  APIKeyCreated,
  User,
  TokenResponse,
  RefreshResponse,
  LoginCredentials,
  MfaRequiredResponse,
} from '$lib/types/user';

// Legacy types (kept for backwards compatibility)
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  key: string;
  user: User;
}

export const authAPI = {
  /**
   * Login with email/password, returns JWT tokens
   */
  login: (credentials: LoginCredentials): Promise<TokenResponse | MfaRequiredResponse> => {
    return apiClient.post<TokenResponse | MfaRequiredResponse>('/api/v1/auth/token', credentials);
  },

  /**
   * Exchange refresh token for new access token
   */
  refresh: (refreshToken: string): Promise<RefreshResponse> => {
    return apiClient.post<RefreshResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    });
  },

  /**
   * Bootstrap authentication for first user (returns JWT tokens)
   */
  bootstrap: (userId: string): Promise<TokenResponse> => {
    return apiClient.post<TokenResponse>('/api/v1/auth/bootstrap', {
      user_id: userId,
    });
  },

  // Legacy endpoints (kept for backwards compatibility)

  /**
   * @deprecated Use login() instead
   */
  loginLegacy: (credentials: LoginRequest): Promise<LoginResponse> => {
    return apiClient.post<LoginResponse>('/api/v1/auth/login', credentials);
  },

  /**
   * @deprecated Use bootstrap() instead
   */
  bootstrapKey: (userId: string): Promise<APIKeyCreated> => {
    return apiClient.post<APIKeyCreated>('/api/v1/auth/keys/bootstrap', {
      user_id: userId,
    });
  },
};
