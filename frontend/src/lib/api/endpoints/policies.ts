import { apiClient } from '../client';
import type { Policy, PolicyCreate, PolicyUpdate, PolicyPreview } from '$lib/types/policy';

export const policiesAPI = {
  list: (): Promise<Policy[]> => {
    return apiClient.get<Policy[]>('/api/v1/policies/');
  },

  get: (id: string): Promise<Policy> => {
    return apiClient.get<Policy>(`/api/v1/policies/${id}`);
  },

  create: (policy: PolicyCreate): Promise<Policy> => {
    return apiClient.post<Policy>('/api/v1/policies/', policy);
  },

  update: (id: string, policy: PolicyUpdate): Promise<Policy> => {
    return apiClient.put<Policy>(`/api/v1/policies/${id}`, policy);
  },

  delete: (id: string): Promise<void> => {
    return apiClient.delete(`/api/v1/policies/${id}`);
  },

  preview: (id: string): Promise<PolicyPreview> => {
    return apiClient.get<PolicyPreview>(`/api/v1/policies/${id}/preview`);
  }
};
