import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { ActiveTask } from "../model/types";
import type { components } from "../../../shared/api/generated/schema";
import { z } from "zod";

export type ConnectedPlatform = components["schemas"]["ConnectedPlatform"];

export async function fetchActiveTasks(): Promise<ActiveTask[]> {
  const res = await apiGet<ActiveTask[]>("tasks/active");
  const data = extractData<ActiveTask[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function cancelActiveTask(taskId: string): Promise<boolean> {
  try {
    const res = await apiPost("tasks/cancel", { task_id: taskId });
    return z.union([
      z.object({ status: z.enum(["ok", "success"]) }),
      z.object({ success: z.literal(true) }),
    ]).safeParse(extractData<unknown>(res)).success;
  } catch {
    return false;
  }
}

export async function fetchConnectedPlatforms(): Promise<ConnectedPlatform[]> {
  const res = await apiGet<unknown>("platforms");
  const parsed = z.array(z.object({
    id: z.string().min(1), type: z.string(), display_name: z.string(), label: z.string().min(1),
  })).safeParse(extractData<unknown>(res));
  if (!parsed.success) throw new Error("平台列表格式不正确，请刷新页面后重试。");
  return parsed.data;
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
  providerId?: string,
  templateName?: string
): Promise<TriggerTaskResult> {
  const payload: Record<string, unknown> = {
    group_id: groupId,
    group_name: groupName,
    platform: platform,
  };
  if (providerId && providerId !== "auto") {
    payload.provider_id = providerId;
  }
  if (templateName && templateName !== "auto") {
    payload.template_name = templateName;
  }
  const res = await apiPost<{ trace_id?: string; message?: string }>("tasks/trigger", payload);


  const result = z.object({
    trace_id: z.string().trim().min(1), message: z.string().optional(), status: z.enum(["ok", "success"]).optional(),
  }).passthrough().safeParse(extractData<unknown>(res));
  if (!result.success) throw new Error("未收到有效的任务提交回执，请刷新任务列表后确认。");
  return {
    status: "ok",
    trace_id: result.data.trace_id,
    data: result.data,
    message: result.data.message || "任务提交成功",
  };
}
