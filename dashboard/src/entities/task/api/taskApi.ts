import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { ActiveTask } from "../model/types";

export async function fetchActiveTasks(): Promise<ActiveTask[]> {
  const res = await apiGet<ActiveTask[]>("tasks/active");
  const data = extractData<ActiveTask[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function cancelActiveTask(taskId: string): Promise<boolean> {
  const res = await apiPost("tasks/cancel", { task_id: taskId });
  return res?.status === "ok";
}

export async function triggerNewTask(
  groupId: string,
  groupName: string = "",
  platform: string = "qq"
): Promise<{ status: string; data?: unknown; message?: string }> {
  const res = await apiPost<{ trace_id: string }>("tasks/trigger", {
    group_id: groupId,
    group_name: groupName,
    platform: platform,
  });
  return {
    status: res?.status || (res?.data ? "ok" : "error"),
    data: res?.data,
    message: res?.message,
  };
}
