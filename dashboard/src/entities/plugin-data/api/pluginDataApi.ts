import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { z } from "zod";
import { configBackupListSchema, configBackupDetailSchema } from "../model/configBackup";

import {
  PluginDataOverview,
  IncrementalBatchesResponse,
  IncrementalBatchItem,
  CheckpointsListResponse,
  CheckpointDetail,
} from "../model/types";

export * from "../model/types";

export async function fetchConfigBackups() {
  const response = await apiGet<unknown>("plugin-data/config-backups");
  return configBackupListSchema.parse(extractData<unknown>(response)).items;
}

export async function fetchConfigBackup(filename: string) {
  const response = await apiGet<unknown>("plugin-data/config-backups/detail", { filename });
  return configBackupDetailSchema.parse(extractData<unknown>(response));
}

export async function fetchPluginDataOverview(): Promise<PluginDataOverview> {
  const res = await apiGet<PluginDataOverview>("plugin-data/overview");
  const data = extractData<PluginDataOverview>(res);
  return (
    data ?? {
      avatars: { count: 0, size_bytes: 0 },
      custom_templates: { count: 0, size_bytes: 0 },
      config_files: { count: 0, size_bytes: 0 },
      config_backups: { count: 0, size_bytes: 0 },
      reports: { count: 0, size_bytes: 0 },
      temp_files: { count: 0, size_bytes: 0 },
    }
  );
}

export async function clearAvatarCache(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/avatars/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearReports(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/reports/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearTempFiles(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/temp/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearCustomTemplates(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/custom-templates/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearConfigFiles(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/config-files/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

export async function clearConfigBackups(): Promise<number> {
  const res = await apiPost<{ deleted: number }>("plugin-data/config-backups/clear", {});
  return extractData<{ deleted: number }>(res)?.deleted ?? 0;
}

// ---------------- 增量批次与游标管理 API ----------------

export async function fetchIncrementalGroups(): Promise<string[]> {
  const res = await apiGet<{ groups: string[] }>("data/incremental/groups");
  const data = extractData<{ groups: string[] }>(res);
  return data?.groups ?? [];
}

export async function fetchIncrementalBatches(
  groupId: string,
  page = 1,
  pageSize = 20,
): Promise<IncrementalBatchesResponse | null> {
  if (!groupId) return null;
  const res = await apiGet<IncrementalBatchesResponse>("data/incremental/batches", {
    group_id: groupId,
    page,
    page_size: pageSize,
  });
  return extractData<IncrementalBatchesResponse>(res);
}

export async function fetchIncrementalBatchDetail(
  groupId: string,
  batchId: string,
): Promise<IncrementalBatchItem | null> {
  if (!groupId || !batchId) return null;
  const res = await apiGet<IncrementalBatchItem>("data/incremental/batch/detail", {
    group_id: groupId,
    batch_id: batchId,
  });
  return extractData<IncrementalBatchItem>(res);
}

export async function deleteIncrementalBatch(groupId: string, batchId: string): Promise<boolean> {
  const res = await apiPost<{ deleted: boolean }>("data/incremental/batch", {
    group_id: groupId,
    batch_id: batchId,
  });
  return extractData<{ deleted: boolean }>(res)?.deleted ?? false;
}

export async function resetIncrementalGroup(
  groupId: string,
): Promise<{ deleted_batches: number; message: string }> {
  const res = await apiPost<{ deleted_batches: number; message: string }>(
    "data/incremental/reset",
    { group_id: groupId },
  );
  return (
    extractData<{ deleted_batches: number; message: string }>(res) ?? {
      deleted_batches: 0,
      message: "Reset completed",
    }
  );
}

// ---------------- 阶段产物 Checkpoint 管理 API ----------------

export async function fetchCheckpointGroups() {
  const res = await apiGet<unknown>("data/checkpoints/groups");
  const data = z
    .object({
      sessions: z.array(
        z.object({ group_id: z.string(), group_name: z.string(), platform: z.string() }),
      ),
    })
    .parse(extractData<unknown>(res));
  return data.sessions;
}

export async function fetchCheckpointsList(params?: {
  limit?: number;
  offset?: number;
  group_id?: string;
  platform?: string;
  date_str?: string;
  stage_name?: string;
  trace_id?: string;
}): Promise<CheckpointsListResponse> {
  const res = await apiGet<CheckpointsListResponse>("data/checkpoints", {
    ...(params ?? {}),
  });
  const data = extractData<CheckpointsListResponse>(res);
  if (!data) throw new Error("快照列表响应为空，请刷新重试。");
  return data;
}

export async function fetchCheckpointDetail(
  groupId: string,
  dateStr: string,
  stageName: string,
  traceId?: string,
): Promise<CheckpointDetail | null> {
  const res = await apiGet<CheckpointDetail | { detail?: CheckpointDetail }>(
    "data/checkpoint/detail",
    {
      group_id: groupId,
      date_str: dateStr,
      stage_name: stageName,
      trace_id: traceId || "",
    },
  );
  if (!res) return null;
  const data = extractData<CheckpointDetail | { detail?: CheckpointDetail }>(res);
  const detail = data && "detail" in data ? data.detail : data;
  const parsed = z
    .object({ group_id: z.string(), date_str: z.string(), stage_name: z.string() })
    .passthrough()
    .safeParse(detail);
  if (!parsed.success) throw new Error("快照详情格式异常，请刷新后重试。");
  return parsed.data;
}

export async function deleteCheckpoint(
  groupId: string,
  dateStr: string,
  stageName?: string,
  traceId?: string,
): Promise<boolean> {
  const res = await apiPost<{ deleted: boolean }>("data/checkpoint", {
    group_id: groupId,
    date_str: dateStr,
    stage_name: stageName || "",
    trace_id: traceId || "",
  });
  return extractData<{ deleted: boolean }>(res)?.deleted ?? false;
}
