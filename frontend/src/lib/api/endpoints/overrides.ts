import { apiClient } from '../client';
import type { Override, OverrideCreate } from '$lib/types/override';

export const overridesAPI = {
  list: (resourceId?: string): Promise<Override[]> => {
    const params = new URLSearchParams();
    if (resourceId) params.append('resource_id', resourceId);
    const query = params.toString();
    return apiClient.get<Override[]>(`/api/v1/overrides/${query ? '?' + query : ''}`);
  },

  create: (data: OverrideCreate): Promise<Override> => {
    return apiClient.post<Override>('/api/v1/overrides/', data);
  },

  cancel: (id: string): Promise<void> => {
    return apiClient.delete<void>(`/api/v1/overrides/${id}`);
  }
};
