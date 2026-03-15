import { apiClient } from '../client';

export interface PricingJobRun {
  id: string;
  provider_type: string;
  status: string;
  trigger: string;
  regions_requested: number | null;
  records_updated: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface ProviderStatus {
  last_run: PricingJobRun | null;
  status: string;
}

export interface PricingStatusSummary {
  next_scheduled_utc: string | null;
  is_running: boolean;
  providers: Record<string, ProviderStatus>;
}

export interface GcpAccountOption {
  id: string;
  name: string;
  project_id: string | null;
}

export interface PricingJobTriggerResponse {
  job_ids: string[];
  message: string;
}

export const pricingJobsAPI = {
  list: (filters?: {
    provider_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PricingJobRun[]> => {
    const params = new URLSearchParams();
    if (filters?.provider_type) params.append('provider_type', filters.provider_type);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.limit) params.append('limit', String(filters.limit));
    if (filters?.offset) params.append('offset', String(filters.offset));
    const query = params.toString();
    return apiClient.get<PricingJobRun[]>(`/api/v1/pricing-jobs/${query ? '?' + query : ''}`);
  },

  getStatus: (): Promise<PricingStatusSummary> => {
    return apiClient.get<PricingStatusSummary>('/api/v1/pricing-jobs/status');
  },

  getGcpAccounts: (): Promise<GcpAccountOption[]> => {
    return apiClient.get<GcpAccountOption[]>('/api/v1/pricing-jobs/gcp-accounts');
  },

  trigger: (providerType?: string, gcpAccountId?: string): Promise<PricingJobTriggerResponse> => {
    return apiClient.post<PricingJobTriggerResponse>(
      '/api/v1/pricing-jobs/trigger',
      {
        provider_type: providerType || null,
        gcp_pricing_account_id: gcpAccountId || null,
      }
    );
  },

  get: (jobId: string): Promise<PricingJobRun> => {
    return apiClient.get<PricingJobRun>(`/api/v1/pricing-jobs/${jobId}`);
  }
};
