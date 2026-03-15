import { apiClient } from '../client';
import type {
  InstanceTypeInfo,
  EstimateRequest,
  EstimateResponse,
  CompareRequest,
  CompareResponse,
  ScheduleEstimateRequest,
  ScheduleEstimateResponse,
} from '$lib/types/calculator';

export const calculatorAPI = {
  getRegions: (provider: string = 'aws'): Promise<string[]> => {
    return apiClient.get<string[]>(`/api/v1/calculator/regions?provider=${provider}`);
  },

  getInstanceTypes: (provider: string = 'aws', region?: string): Promise<InstanceTypeInfo[]> => {
    const params = new URLSearchParams({ provider });
    if (region) params.append('region', region);
    return apiClient.get<InstanceTypeInfo[]>(`/api/v1/calculator/instance-types?${params}`);
  },

  estimate: (request: EstimateRequest): Promise<EstimateResponse> => {
    return apiClient.post<EstimateResponse>('/api/v1/calculator/estimate', {
      provider: request.provider || 'aws',
      ...request,
    });
  },

  compare: (request: CompareRequest): Promise<CompareResponse> => {
    return apiClient.post<CompareResponse>('/api/v1/calculator/compare', request);
  },

  scheduleEstimate: (request: ScheduleEstimateRequest): Promise<ScheduleEstimateResponse> => {
    return apiClient.post<ScheduleEstimateResponse>('/api/v1/calculator/schedule-estimate', {
      provider: request.provider || 'aws',
      ...request,
    });
  },
};
