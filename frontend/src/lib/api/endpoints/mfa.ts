import { apiClient } from '../client';
import type { MfaSetupResponse, MfaStatusResponse, TokenResponse } from '$lib/types/user';

export const mfaAPI = {
  status: (): Promise<MfaStatusResponse> => {
    return apiClient.get<MfaStatusResponse>('/api/v1/auth/mfa/status');
  },

  setup: (): Promise<MfaSetupResponse> => {
    return apiClient.post<MfaSetupResponse>('/api/v1/auth/mfa/setup', {});
  },

  verify: (code: string): Promise<MfaStatusResponse> => {
    return apiClient.post<MfaStatusResponse>('/api/v1/auth/mfa/verify', { code });
  },

  disable: (password: string, code: string): Promise<MfaStatusResponse> => {
    return apiClient.post<MfaStatusResponse>('/api/v1/auth/mfa/disable', { password, code });
  },

  validate: (mfaToken: string, code: string): Promise<TokenResponse> => {
    return apiClient.post<TokenResponse>('/api/v1/auth/mfa/validate', {
      mfa_token: mfaToken,
      code,
    });
  },
};
