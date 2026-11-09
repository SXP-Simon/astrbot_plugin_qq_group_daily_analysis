import { apiGet, apiPost, extractData } from "@/shared/api/bridge";
import { cdnBaseUrlSchema } from "@/entities/config/model/renderingConfig";
import {
  templateResourceFileSchema,
  templateResourceStatusSchema,
} from "@/entities/config/model/templateResources";

export async function fetchTemplateResources() {
  const response = await apiGet<unknown>("config/template-resources");
  const parsed = templateResourceStatusSchema.safeParse(extractData(response));
  if (!parsed.success) throw new Error(response?.message || "未能读取模板素材，请刷新重试。");
  return parsed.data;
}

export async function downloadTemplateResource(
  name: string,
  cdnBaseUrl: string,
  downloadId?: string,
) {
  const cdn = cdnBaseUrlSchema.safeParse(cdnBaseUrl);
  if (!cdn.success) throw new Error(cdn.error.issues[0].message);
  const response = await apiPost<unknown>("config/template-resources/download", {
    name,
    cdn_base_url: cdn.data,
    ...(downloadId ? { download_id: downloadId } : {}),
  });
  const parsed = templateResourceFileSchema.safeParse(extractData(response));
  if (!parsed.success || !parsed.data.available || parsed.data.name !== name) {
    const envelope = extractData<unknown>(response);
    const message =
      envelope && typeof envelope === "object" && "message" in envelope
        ? envelope.message
        : response?.message;
    throw new Error(
      typeof message === "string" ? message : "素材下载失败，可更换 CDN 重试；已下载的文件会保留。",
    );
  }
  return parsed.data;
}
