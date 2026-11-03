import { z } from "zod";
import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import type { components } from "../../../shared/api/generated/schema";

export type RecordLocator = components["schemas"]["RecordLocator"];
export type ManagedRecord = components["schemas"]["ManagedRecord"];
export type ManagedRecordMutation = components["schemas"]["ManagedRecordMutation"];
export type ManagedRecordEntry = components["schemas"]["ManagedRecordEntry"];

export const recordLocatorSchema: z.ZodType<RecordLocator> = z.object({
  kind: z.enum(["history", "batch", "checkpoint", "avatar"]), key: z.string().optional(), group_id: z.string().optional(),
  batch_id: z.string().optional(), date_str: z.string().optional(), stage_name: z.string().optional(), trace_id: z.string().optional(),
});
export const managedRecordSchema: z.ZodType<ManagedRecord> = z.object({ locator: recordLocatorSchema, data: z.json(), revision: z.string() });

export async function fetchManagedRecords(kind: string, search: string, page: number) {
  const response = await apiGet("plugin-data/records", { kind, search, page });
  return z.object({ items: z.array(z.object({ locator: recordLocatorSchema, name: z.string(), size_bytes: z.number() })), total: z.number() }).parse(extractData<unknown>(response));
}

export async function fetchManagedRecord(locator: RecordLocator) {
  const response = await apiGet("plugin-data/records/detail", locator);
  // 记录本身也含 data，必须先按结构识别，避免把业务产物误当成响应信封。
  for (const candidate of [response?.data, extractData<unknown>(response), response]) {
    const parsed = managedRecordSchema.safeParse(candidate);
    if (parsed.success) return parsed.data;
    const error = z.object({ status: z.literal("error"), message: z.string() }).safeParse(candidate);
    if (error.success) throw new Error(error.data.message);
  }
  throw new Error("记录内容格式异常，请刷新后重试");
}

export async function mutateManagedRecord(input: ManagedRecordMutation) {
  const response = await apiPost("plugin-data/records/mutate", input);
  const data = extractData<unknown>(response);
  if (!z.object({ success: z.literal(true) }).safeParse(data).success) {
    const error = z.object({ message: z.string() }).safeParse(data);
    throw new Error(error.success ? error.data.message : "记录操作未完成，请刷新后重试");
  }
}

export { recordKey } from "../model/managedRecord";
