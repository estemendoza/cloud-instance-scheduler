export interface Organization {
  id: string; // UUID
  name: string;
  slug: string;
}

export interface OrganizationCreate {
  name: string;
  slug: string;
}

export interface OrganizationUpdate {
  name?: string;
  slug?: string;
}
