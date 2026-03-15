// Schedule types
export interface TimeWindow {
  start: string; // "HH:MM" format
  end: string;   // "HH:MM" format
}

export type DayOfWeek = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';

export type WeeklySchedule = {
  [K in DayOfWeek]?: TimeWindow[];
};

// Cron schedule type
export interface CronSchedule {
  start: string; // cron expression for when to start
  stop: string;  // cron expression for when to stop
}

export type ScheduleType = 'weekly' | 'cron';

// Resource selector types
export interface TagSelector {
  tags: Record<string, string>;
}

export interface ResourceIdSelector {
  resource_ids: string[];
}

export type ResourceSelector = TagSelector | ResourceIdSelector;

// Policy types
export interface Policy {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  timezone: string;
  schedule_type: ScheduleType;
  schedule: WeeklySchedule | CronSchedule;
  resource_selector: ResourceSelector;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PolicyCreate {
  name: string;
  description?: string;
  timezone: string;
  schedule_type?: ScheduleType;
  schedule: WeeklySchedule | CronSchedule;
  resource_selector: ResourceSelector;
  is_enabled?: boolean;
}

export interface PolicyUpdate {
  name?: string;
  description?: string;
  timezone?: string;
  schedule_type?: ScheduleType;
  schedule?: WeeklySchedule | CronSchedule;
  resource_selector?: ResourceSelector;
  is_enabled?: boolean;
}

export interface PolicyPreview {
  policy_id: string;
  affected_resource_count: number;
  sample_resources: string[];
}

// Helper constants
export const DAYS_OF_WEEK: DayOfWeek[] = [
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
];

export const DAY_LABELS: Record<DayOfWeek, string> = {
  monday: 'Mon',
  tuesday: 'Tue',
  wednesday: 'Wed',
  thursday: 'Thu',
  friday: 'Fri',
  saturday: 'Sat',
  sunday: 'Sun'
};
