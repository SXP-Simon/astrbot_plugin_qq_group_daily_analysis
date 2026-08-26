import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { ActiveTask } from "../model/types";

export interface ConnectedPlatform {
  id: string;
  name: string;
  type: string;
  label: string;
}

export async function fetchActiveTasks(): Promise<ActiveTask[]> {
  const res = await apiGet<ActiveTask[]>("tasks/active");
  const data = extractData<ActiveTask[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function cancelActiveTask(taskId: string): Promise<boolean> {
  const res = await apiPost("tasks/cancel", { task_id: taskId });
  if (!res) return false;
  const raw = res as Record<string, unknown>;
  const nestedData = raw.data as Record<string, unknown> | undefined;
  return (
    raw.status === "ok" ||
    raw.status === "success" ||
    raw.status === 200 ||
    nestedData?.status === "ok" ||
    nestedData?.status === "success"
  );
}

export async function fetchConnectedPlatforms(): Promise<ConnectedPlatform[]> {
  const res = await apiGet<ConnectedPlatform[]>("platforms");
  const data = extractData<ConnectedPlatform[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export interface TriggerTaskResult {
  status: string;
  trace_id?: string;
  message?: string;
  data?: unknown;
}

export async function triggerNewTask(
  groupId: string,
  groupName: string = "",
  platform: string = "auto",
  providerId?: string
): Promise<TriggerTaskResult> {
  const payload: Record<string, unknown> = {
    group_id: groupId,
    group_name: groupName,
    platform: platform,
  };
  if (providerId && providerId !== "auto") {
    payload.provider_id = providerId;
  }
  const res = await apiPost<{ trace_id?: string; message?: string }>("tasks/trigger", payload);

  const data = extractData<{ trace_id?: string; message?: string }>(res);
  const rawObj = (res && typeof res === "object" ? res : {}) as Record<string, unknown>;
  const traceId = data?.trace_id || (rawObj.trace_id as string | undefined);
  const isOk =
    rawObj.status === "ok" ||
    rawObj.status === "success" ||
    !!traceId ||
    (typeof rawObj.message === "string" && rawObj.message.includes("successfully"));

  return {
    status: isOk ? "ok" : "error",
    trace_id: traceId,
    data: data || undefined,
    message: data?.message || (rawObj.message as string | undefined) || (isOk ? "任务提交成功" : "任务提交失败"),
  };
}
