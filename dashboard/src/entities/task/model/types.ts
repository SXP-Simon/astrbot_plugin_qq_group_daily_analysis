export interface ActiveTask {
  task_id: string;
  group_id: string;
  group_name: string;
  platform: string;
  trigger_type: string;
  current_stage: string;
  started_at: number;
  duration_s: number;
  last_heartbeat: number;
}
