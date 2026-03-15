import { apiClient } from '../client';

export interface SystemStatus {
  bootstrapped: boolean;
  version: string;
}

export const systemAPI = {
  getStatus: (): Promise<SystemStatus> => {
    return apiClient.get<SystemStatus>('/api/v1/system/status');
  }
};
