import { apiClient } from '../client';
import type { APIKey, APIKeyCreate, APIKeyCreated } from '$lib/types/apiKey';

export const apiKeysAPI = {
  list: (): Promise<APIKey[]> => {
    return apiClient.get<APIKey[]>('/api/v1/auth/keys');
  },

  create: (data: APIKeyCreate): Promise<APIKeyCreated> => {
    return apiClient.post<APIKeyCreated>('/api/v1/auth/keys', data);
  },

  delete: (keyId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/auth/keys/${keyId}`);
  }
};
