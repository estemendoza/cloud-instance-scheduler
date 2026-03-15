import { apiClient } from '../client';
import type { Resource, ResourceFilter, PaginatedResources } from '$lib/types/resource';

export const resourcesAPI = {
  list: (filters?: ResourceFilter): Promise<PaginatedResources> => {
    const params = new URLSearchParams();
    if (filters?.provider_type) params.append('provider_type', filters.provider_type);
    if (filters?.state) params.append('state', filters.state);
    if (filters?.cloud_account_id) params.append('cloud_account_id', filters.cloud_account_id);
    if (filters?.region) params.append('region', filters.region);
    if (filters?.page) params.append('page', filters.page.toString());
    if (filters?.page_size) params.append('page_size', filters.page_size.toString());

    const query = params.toString();
    return apiClient.get<PaginatedResources>(`/api/v1/resources/${query ? '?' + query : ''}`);
  },

  get: (id: string): Promise<Resource> => {
    return apiClient.get<Resource>(`/api/v1/resources/${id}`);
  }
};
