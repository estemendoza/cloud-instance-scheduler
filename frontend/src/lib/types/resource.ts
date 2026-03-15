export interface Resource {
  id: string; // UUID
  organization_id: string; // UUID
  cloud_account_id: string; // UUID
  provider_resource_id: string;
  name: string | null;
  resource_type: string;
  region: string;
  state: string;
  tags: Record<string, string> | null;
  instance_type: string | null;
  provider_type: string | null;
  last_seen_at: string; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface ResourceFilter {
  provider_type?: string;
  state?: string;
  cloud_account_id?: string;
  region?: string;
  page?: number;
  page_size?: number;
}

export interface PaginatedResources {
  items: Resource[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
