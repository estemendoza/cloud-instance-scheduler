export interface InstanceTypeInfo {
  instance_type: string;
  hourly_rate: number;
  region: string;
}

export interface EstimateRequest {
  provider?: string;
  region: string;
  instance_type: string;
  hours_per_day: number;
  days_per_week: number;
}

export interface EstimateResponse {
  instance_type: string;
  region: string;
  hourly_rate: number;
  hours_per_day: number;
  days_per_week: number;
  daily_cost: number;
  weekly_cost: number;
  monthly_cost: number;
  annual_cost: number;
  currency: string;
  error?: string;
}

export interface CompareInstanceRequest {
  provider?: string;
  region: string;
  instance_type: string;
}

export interface CompareRequest {
  instances: CompareInstanceRequest[];
  hours_per_day: number;
  days_per_week: number;
}

export interface CompareResponse {
  estimates: EstimateResponse[];
}

export interface TimeWindow {
  start: string;
  end: string;
}

export interface WeeklySchedule {
  monday?: TimeWindow[];
  tuesday?: TimeWindow[];
  wednesday?: TimeWindow[];
  thursday?: TimeWindow[];
  friday?: TimeWindow[];
  saturday?: TimeWindow[];
  sunday?: TimeWindow[];
}

export interface ScheduleEstimateRequest {
  provider?: string;
  region: string;
  instance_type: string;
  schedule: WeeklySchedule;
}

export interface Vs24x7 {
  monthly_24x7_cost: number;
  monthly_savings: number;
  savings_percent: number;
}

export interface ScheduleEstimateResponse {
  instance_type: string;
  region: string;
  hourly_rate: number;
  running_hours_per_week: number;
  weekly_cost: number;
  monthly_cost: number;
  annual_cost: number;
  vs_24x7: Vs24x7;
  currency: string;
  error?: string;
}
