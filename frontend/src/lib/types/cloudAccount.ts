export interface CloudAccount {
  id: string;
  organization_id: string;
  name: string;
  provider_type: string;
  is_active: boolean;
  selected_regions: string[] | null;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
  credential_hints?: Record<string, string> | null;
}

export interface CloudAccountCreate {
  name: string;
  provider_type: string;
  credentials: Record<string, string>;
  is_active?: boolean;
  selected_regions?: string[] | null;
}

export interface CloudAccountUpdate {
  name?: string;
  is_active?: boolean;
  credentials?: Record<string, string>;
  selected_regions?: string[] | null;
}

export interface SyncResult {
  created: number;
  updated: number;
  total: number;
  accounts_synced?: number;
}
