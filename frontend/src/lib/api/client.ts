import {
  APIError,
  UnauthorizedError,
  ForbiddenError,
  NotFoundError,
  ValidationError
} from './errors';

export class APIClient {
  private baseURL: string;
  private accessToken: string | null = null;
  private isRefreshing: boolean = false;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  /**
   * Set the access token for Bearer authentication
   */
  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  /**
   * @deprecated Use setAccessToken instead
   */
  setApiKey(key: string | null) {
    this.accessToken = key;
  }

  /**
   * Try to refresh the access token using the stored refresh token
   */
  private async tryRefreshToken(): Promise<string | null> {
    // Avoid multiple simultaneous refresh attempts
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    this.refreshPromise = this.doRefreshToken();

    try {
      return await this.refreshPromise;
    } finally {
      this.isRefreshing = false;
      this.refreshPromise = null;
    }
  }

  private async doRefreshToken(): Promise<string | null> {
    if (typeof window === 'undefined') return null;

    const refreshToken = localStorage.getItem('refreshToken');
    if (!refreshToken) return null;

    try {
      // Make refresh request without using this.request to avoid recursion
      const response = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        // Refresh failed - clear tokens
        localStorage.removeItem('refreshToken');
        this.accessToken = null;
        return null;
      }

      const data = await response.json();
      this.accessToken = data.access_token;

      // Update auth store if available
      try {
        const { authStore } = await import('$lib/stores/auth');
        authStore.setAccessToken(data.access_token);
      } catch {
        // Store not available, just update local token
      }

      return data.access_token;
    } catch {
      return null;
    }
  }

  async request<T>(
    endpoint: string,
    options?: RequestInit,
    isRetry: boolean = false
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    // Merge any additional headers from options
    if (options?.headers) {
      const optHeaders = options.headers as Record<string, string>;
      Object.assign(headers, optHeaders);
    }

    const url = `${this.baseURL}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle error responses
      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        let errorDetails;

        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
          errorDetails = errorData;
        } catch {
          // If response is not JSON, use text
          const text = await response.text();
          if (text) errorMessage = text;
        }

        // Handle 401 - try to refresh token and retry once
        if (response.status === 401 && !isRetry) {
          const newToken = await this.tryRefreshToken();
          if (newToken) {
            // Retry the request with new token
            return this.request<T>(endpoint, options, true);
          }
        }

        // Throw specific error types
        switch (response.status) {
          case 401:
            throw new UnauthorizedError(errorMessage);
          case 403:
            throw new ForbiddenError(errorMessage);
          case 404:
            throw new NotFoundError(errorMessage);
          case 422:
            throw new ValidationError(errorMessage, errorDetails);
          default:
            throw new APIError(response.status, errorMessage, errorDetails);
        }
      }

      // Handle empty responses (204 No Content)
      if (response.status === 204) {
        return {} as T;
      }

      // Parse JSON response
      return await response.json();
    } catch (error) {
      // Re-throw API errors as-is
      if (error instanceof APIError) {
        throw error;
      }

      // Wrap network errors
      throw new APIError(0, `Network error: ${error}`);
    }
  }

  // Convenience methods
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

// Export a singleton instance
// In production, use relative URLs (empty string) so nginx proxies /api to backend
// In development, use localhost:8000 directly
export const apiClient = new APIClient(
  import.meta.env.PUBLIC_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
);
