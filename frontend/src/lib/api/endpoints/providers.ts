import { apiClient } from '../client';

export interface CredentialFieldDef {
  key: string;
  label: string;
  type: string;       // "text" | "password" | "textarea"
  required: boolean;
  secret: boolean;
  placeholder: string;
}

export interface RegionDef {
  code: string;
  name: string;
}

export interface ProviderMetadata {
  provider_type: string;
  display_name: string;
  color: string;
  region_label: string;
  credential_fields: CredentialFieldDef[];
  regions: RegionDef[];
}

export const providersAPI = {
  getMetadata: (): Promise<ProviderMetadata[]> => {
    return apiClient.get<ProviderMetadata[]>('/api/v1/providers/metadata');
  }
};
