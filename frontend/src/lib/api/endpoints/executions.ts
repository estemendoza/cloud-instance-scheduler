import { apiClient } from '../client';
import type {
  Execution,
  ExecutionStatistics,
  ExecutionSummary,
  ExecutionFilter
} from '$lib/types/execution';

export const executionsAPI = {
  list: (filters?: ExecutionFilter): Promise<Execution[]> => {
    const params = new URLSearchParams();
    if (filters?.resource_id) params.append('resource_id', filters.resource_id);
    if (filters?.action) params.append('action', filters.action);
    if (filters?.success !== undefined) params.append('success', String(filters.success));
    if (filters?.status) params.append('status', filters.status);
    if (filters?.hours) params.append('hours', String(filters.hours));
    if (filters?.limit) params.append('limit', String(filters.limit));
    if (filters?.offset) params.append('offset', String(filters.offset));

    const query = params.toString();
    return apiClient.get<Execution[]>(`/api/v1/executions/${query ? '?' + query : ''}`);
  },

  getCount: (filters?: ExecutionFilter): Promise<{ total: number }> => {
    const params = new URLSearchParams();
    if (filters?.resource_id) params.append('resource_id', filters.resource_id);
    if (filters?.action) params.append('action', filters.action);
    if (filters?.success !== undefined) params.append('success', String(filters.success));
    if (filters?.status) params.append('status', filters.status);
    if (filters?.hours) params.append('hours', String(filters.hours));

    const query = params.toString();
    return apiClient.get<{ total: number }>(`/api/v1/executions/count${query ? '?' + query : ''}`);
  },

  getStatistics: (hours: number = 24): Promise<ExecutionStatistics> => {
    return apiClient.get<ExecutionStatistics>(`/api/v1/executions/statistics?hours=${hours}`);
  },

  getSummary: (): Promise<ExecutionSummary> => {
    return apiClient.get<ExecutionSummary>('/api/v1/executions/summary');
  },

  getResourceTimeline: (resourceId: string, limit: number = 50, offset: number = 0): Promise<Execution[]> => {
    return apiClient.get<Execution[]>(
      `/api/v1/executions/resources/${resourceId}/timeline?limit=${limit}&offset=${offset}`
    );
  },

  getResourceTimelineCount: (resourceId: string): Promise<{ total: number }> => {
    return apiClient.get<{ total: number }>(
      `/api/v1/executions/resources/${resourceId}/timeline/count`
    );
  }
};
