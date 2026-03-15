export interface Execution {
  id: string; // UUID
  organization_id: string; // UUID
  resource_id: string; // UUID
  action: string; // "START" | "STOP"
  desired_state: string;
  actual_state_before: string;
  status: string; // "pending" | "completed" | "failed"
  success: boolean;
  error_message: string | null;
  executed_at: string; // ISO datetime
}

export interface ExecutionStatistics {
  total_executions: number;
  successful: number;
  failed: number;
  success_rate: number; // 0.0 - 1.0
  actions: Record<string, number>; // {"START": count, "STOP": count}
  period_hours: number;
}

export interface ExecutionSummary {
  last_hour: ExecutionStatistics;
  last_24_hours: ExecutionStatistics;
  last_7_days: ExecutionStatistics;
  recent_failures_count: number;
  last_execution_at: string | null; // ISO datetime
}

export interface ExecutionFilter {
  resource_id?: string;
  action?: string;
  success?: boolean;
  status?: string;
  hours?: number;
  limit?: number;
  offset?: number;
}
