export interface Override {
  id: string;
  organization_id: string;
  resource_id: string;
  desired_state: 'RUNNING' | 'STOPPED';
  expires_at: string;
  reason: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface OverrideCreate {
  resource_id: string;
  desired_state: 'RUNNING' | 'STOPPED';
  expires_at: string;
  reason?: string;
}
