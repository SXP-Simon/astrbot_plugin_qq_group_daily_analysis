import { z } from "zod";
import { apiGet, apiPost, apiUpload, extractData } from "../../../shared/api/bridge";
import {
  wordCloudCatalogSchema,
  wordCloudPreviewSchema,
  wordCloudSnapshotSchema,
  type WordCloudOptions,
  type WordCloudPreviewSource,
} from "../model/types";

/** 宿主桥接未回包时也必须结束等待；超时后的响应不会再次更新预览。 */
async function awaitPreviewResponse<T>(pending: Promise<T>, timeoutMs: number, timeoutMessage: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      pending,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function parseResponse<T>(response: unknown, schema: z.ZodType<T>): T {
  const parsed = schema.safeParse(extractData<unknown>(response));
  if (parsed.success) return parsed.data;
  let envelope: unknown = response;
  for (let depth = 0; depth < 2; depth += 1) {
    if (!envelope || typeof envelope !== "object") break;
    if ("message" in envelope && typeof envelope.message === "string" && envelope.message) {
      throw new Error(envelope.message);
    }
    envelope = "data" in envelope ? envelope.data : null;
  }
  throw new Error("词云服务返回了无效数据，请刷新页面后重试");
}

export async function fetchWordCloudCatalog() {
  return parseResponse(await awaitPreviewResponse(apiGet("wordcloud/templates"), 30000, "读取词云模板和字体超时，请重试"), wordCloudCatalogSchema);
}

export async function previewWordCloud(options: WordCloudOptions, mode: "html" | "image", source?: WordCloudPreviewSource) {
  const response = await awaitPreviewResponse(
    apiPost("wordcloud/preview", { options, mode, ...source }),
    mode === "html" ? 30000 : 120000,
    mode === "html" ? "请求词云预览超时，请刷新预览后重试" : "T2I 图片预览超时，请稍后重试",
  );
  const result = parseResponse(response, wordCloudPreviewSchema);
  if (!result[mode]) throw new Error(mode === "html" ? "未收到词云预览内容" : "未收到 T2I 预览图片");
  return result;
}

export async function uploadWordCloudFont(file: File) {
  return parseResponse(await apiUpload("wordcloud/fonts", file), z.object({ id: z.string(), label: z.string() }));
}

export async function fetchWordCloudSnapshots() {
  return parseResponse(await awaitPreviewResponse(apiGet("wordcloud/snapshots"), 30000, "读取群聊缓存超时，请重试"), z.object({ snapshots: z.array(wordCloudSnapshotSchema) })).snapshots;
}

export async function previewWordCloudFont(font: string) {
  return parseResponse(await awaitPreviewResponse(apiPost("wordcloud/fonts/preview", { font }), 30000, "字体样张加载超时，请刷新预览后重试"), z.object({ html: z.string(), font: z.string() }));
}

export async function renameWordCloudFont(id: string, label: string) {
  return parseResponse(await apiPost("wordcloud/fonts/rename", { id, label }), z.object({ id: z.string(), label: z.string() }));
}

export async function deleteWordCloudFont(id: string) {
  return parseResponse(await apiPost("wordcloud/fonts/delete", { id }), z.object({ id: z.string(), deleted: z.literal(true) }));
}

export async function restoreWordCloudFont(id: string) {
  return parseResponse(await apiPost("wordcloud/fonts/restore", { id }), z.object({ id: z.string(), label: z.string() }));
}
