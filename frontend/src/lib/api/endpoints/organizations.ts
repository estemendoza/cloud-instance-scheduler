import { apiClient } from '../client';
import type { Organization, OrganizationCreate, OrganizationUpdate } from '$lib/types/organization';

export const organizationsAPI = {
  create: (data: OrganizationCreate): Promise<Organization> => {
    return apiClient.post<Organization>('/api/v1/organizations/', data);
  },

  get: (id: string): Promise<Organization> => {
    return apiClient.get<Organization>(`/api/v1/organizations/${id}`);
  },

  list: (): Promise<Organization[]> => {
    return apiClient.get<Organization[]>('/api/v1/organizations/');
  },

  update: (id: string, data: OrganizationUpdate): Promise<Organization> => {
    return apiClient.put<Organization>(`/api/v1/organizations/${id}`, data);
  }
};
