import type { Organization } from './organization';

export type UserRole = 'admin' | 'operator' | 'viewer';

export interface User {
  id: string; // UUID
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  organization_id: string; // UUID
  organization?: Organization;
  mfa_enabled?: boolean;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
  role: UserRole;
  is_active?: boolean;
  organization_id: string; // UUID
}

export interface UserUpdate {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Admin',
  operator: 'Operator',
  viewer: 'Viewer'
};

export const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  admin: 'Full access to all settings and operations',
  operator: 'Can manage resources and schedules',
  viewer: 'Read-only access to dashboards'
};

export interface APIKey {
  id: string; // UUID
  name: string;
  prefix: string;
  created_at: string; // ISO datetime
  last_used_at: string | null; // ISO datetime
  expires_at: string | null; // ISO datetime
}

export interface APIKeyCreated extends APIKey {
  key: string; // The plain text key (only returned once)
}

export interface APIKeyCreate {
  name: string;
  expires_at?: string; // ISO datetime
  user_id: string; // UUID
}

// JWT Authentication types
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

// MFA types
export interface MfaRequiredResponse {
  mfa_required: boolean;
  mfa_token: string;
}

export interface MfaSetupResponse {
  secret: string;
  provisioning_uri: string;
}

export interface MfaStatusResponse {
  enabled: boolean;
}

export interface ProfileUpdate {
  full_name?: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}
