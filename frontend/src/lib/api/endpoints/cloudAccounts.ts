import { apiClient } from '../client';
import type { CloudAccount, CloudAccountCreate, CloudAccountUpdate, SyncResult } from '$lib/types/cloudAccount';

export const cloudAccountsAPI = {
  list: (): Promise<CloudAccount[]> => {
    return apiClient.get<CloudAccount[]>('/api/v1/cloud-accounts/');
  },

  get: (id: string): Promise<CloudAccount> => {
    return apiClient.get<CloudAccount>(`/api/v1/cloud-accounts/${id}`);
  },

  create: (account: CloudAccountCreate): Promise<CloudAccount> => {
    return apiClient.post<CloudAccount>('/api/v1/cloud-accounts/', account);
  },

  update: (id: string, account: CloudAccountUpdate): Promise<CloudAccount> => {
    return apiClient.put<CloudAccount>(`/api/v1/cloud-accounts/${id}`, account);
  },

  delete: (id: string): Promise<void> => {
    return apiClient.delete(`/api/v1/cloud-accounts/${id}`);
  },

  sync: (id: string): Promise<SyncResult> => {
    return apiClient.post<SyncResult>(`/api/v1/cloud-accounts/${id}/sync`, {});
  }
};
