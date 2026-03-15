import { apiClient } from '../client';
import type { OrganizationSavings, ResourceSavings } from '$lib/types/savings';

export const savingsAPI = {
  getOrganizationSavings: (): Promise<OrganizationSavings> => {
    return apiClient.get<OrganizationSavings>('/api/v1/savings/organization');
  },

  getResourceSavings: (resourceId: string): Promise<ResourceSavings> => {
    return apiClient.get<ResourceSavings>(`/api/v1/savings/resources/${resourceId}`);
  }
};
