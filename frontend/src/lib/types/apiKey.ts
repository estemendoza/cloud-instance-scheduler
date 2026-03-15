export interface APIKey {
  id: string;
  prefix: string;
  name: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  days_until_expiry: number | null;
  expires_soon: boolean;
}

export interface APIKeyCreate {
  name: string;
  expires_at?: string | null;
}

export interface APIKeyCreated extends APIKey {
  key: string; // Plain text key, shown only once
}
