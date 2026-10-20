import { apiGet, extractData } from "../../../shared/api/bridge";

const previews = new Map<string, Promise<string | null>>();
export type ComicPreviewVariant = "thumbnail" | "full";

/** 通过宿主鉴权桥接获取本地示例图，成功结果按模板复用。 */
export async function fetchComicTemplatePreview(templateId: string, variant: ComicPreviewVariant = "full", refresh = false): Promise<string | null> {
  const key = `${templateId}:${variant}`;
  if (refresh) previews.delete(key);
  const cached = previews.get(key);
  if (cached) return cached;

  const request = (async () => {
    const response = await apiGet<{ data_url: string | null }>("comic/templates/preview", {
      template_name: templateId,
      variant,
    });
    const data = extractData<unknown>(response);
    if (response?.status !== "error" && data && typeof data === "object" && "data_url" in data) {
      if (data.data_url === null) return null;
      if (typeof data.data_url === "string" && /^data:image\/(webp|png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(data.data_url)) {
        return data.data_url;
      }
    }
    const detail = data && typeof data === "object" && "message" in data && typeof data.message === "string"
      ? data.message : response?.message;
    throw new Error(detail || "未收到有效的漫画示例图响应");
  })();
  previews.set(key, request);
  try {
    return await request;
  } catch (error) {
    if (previews.get(key) === request) previews.delete(key);
    throw error;
  }
}
