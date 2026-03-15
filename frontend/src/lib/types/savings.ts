export interface ResourceSavings {
  resource_id: string;
  instance_type: string;
  hourly_rate: number;
  stopped_hours_per_week: number;
  monthly_savings: number;
  annual_savings: number;
  currency: string; // "USD"
  policy_name: string | null;
  note: string | null;
}

export interface OrganizationSavings {
  total_monthly_savings: number;
  total_annual_savings: number;
  currency: string; // "USD"
  resources_with_savings: number;
  total_resources: number;
}
