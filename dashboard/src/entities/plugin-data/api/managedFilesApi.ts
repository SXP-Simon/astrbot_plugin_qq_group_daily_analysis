import { z } from "zod";
import { apiGet, apiPost, apiUpload, extractData } from "../../../shared/api/bridge";
import type { components } from "../../../shared/api/generated/schema";

export type ManagedPartition = components["schemas"]["ManagedPartition"];
export type ManagedFile = components["schemas"]["ManagedFile"];
export type ManagedFileContent = components["schemas"]["ManagedFileContent"];
export type ManagedFileMutation = components["schemas"]["ManagedFileMutation"];
export type ManagedFileGroup = components["schemas"]["ManagedFileGroup"];

const partitionSchema: z.ZodType<ManagedPartition> = z.object({
  key: z.string(), name: z.string(), directory: z.string(), description: z.string(), impact: z.string(),
  writable: z.boolean(), deletable: z.boolean(), count: z.number(), size_bytes: z.number(),
});
const fileSchema: z.ZodType<ManagedFile> = z.object({
  name: z.string(), size_bytes: z.number(), modified_at: z.number(), media_type: z.string(),
  editable: z.boolean(), downloadable: z.boolean(),
  revision: z.string(),
});
const contentSchema: z.ZodType<ManagedFileContent> = z.object({
  name: z.string(), content_base64: z.string(), text: z.string().nullable(), revision: z.string(), media_type: z.string(),
});

function checkedData(response: unknown): unknown {
  const data = extractData<unknown>(response);
  for (const layer of [response, data]) {
    const error = z.object({ status: z.literal("error"), message: z.string().optional() }).safeParse(layer);
    if (error.success) throw new Error(error.data.message || "文件操作失败");
  }
  return data;
}

export async function fetchManagedPartitions() {
  return z.object({ items: z.array(partitionSchema) }).parse(checkedData(await apiGet("plugin-data/partitions"))).items;
}

export async function fetchManagedFiles(partition: string, search: string, page: number, extensions = "", directory = "") {
  return z.object({ items: z.array(fileSchema), total: z.number(), groups: z.array(z.object({ directory: z.string(), count: z.number(), size_bytes: z.number() })).optional() }).parse(checkedData(
    await apiGet("plugin-data/files", { partition, search, page, page_size: 20, extensions, directory })));
}

export async function fetchManagedContent(partition: string, name: string) {
  return contentSchema.parse(checkedData(await apiGet("plugin-data/files/content", { partition, name })));
}

export async function mutateManagedFile(body: ManagedFileMutation) {
  const result = checkedData(await apiPost("plugin-data/files/mutate", body));
  if (!z.object({ success: z.literal(true) }).safeParse(result).success) throw new Error("文件操作未完成，请刷新后重试");
}

export async function startManagedUpload(body: { download_id: string; partition: string; name: string; operation: "create" | "replace"; revision: string; total: number }) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const response = await Promise.race([apiPost("plugin-data/files/upload/start", body), new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("上传初始化超过 10 秒未收到回执，请检查连接后重试")), 10_000);
    })]);
    const result = z.object({ upload_id: z.string() }).parse(checkedData(response));
    if (result.upload_id !== body.download_id) throw new Error("上传初始化回执不匹配");
  } finally { clearTimeout(timer); }
}

export async function uploadManagedChunk(file: File, uploadId: string, offset: number) {
  const response = await apiUpload(`plugin-data/files/upload/${encodeURIComponent(uploadId)}/${offset}`, file);
  return z.object({ received: z.number().int().positive(), total: z.number().int().positive(), complete: z.boolean() }).parse(checkedData(response));
}

export async function deleteManagedFiles(partition: string, files: Pick<ManagedFile, "name" | "revision">[]) {
  const result = checkedData(await apiPost("plugin-data/files/delete-many", { partition, files }));
  return z.object({ deleted: z.array(z.string()), failed: z.array(z.object({ name: z.string(), message: z.string() })) }).parse(result);
}
