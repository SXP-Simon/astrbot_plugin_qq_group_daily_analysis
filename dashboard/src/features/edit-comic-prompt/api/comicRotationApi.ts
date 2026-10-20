import { z } from "zod";
import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import type { ComicTemplateRotationStatus } from "../model/comicTemplateRotation";

const rotationStatusSchema: z.ZodType<ComicTemplateRotationStatus> = z.object({
  mode: z.enum(["fixed", "sequential", "daily_sequential", "random", "daily_random", "shuffle"]),
  scope: z.enum(["global", "group"]),
  scope_key: z.string(),
  candidates: z.array(z.string()),
  current_template_id: z.string().nullable(),
  current_template_name: z.string().nullable(),
  next_template_id: z.string().nullable(),
  next_template_name: z.string().nullable(),
  date: z.string(),
  initialized: z.boolean(),
  warning: z.string().nullable(),
});

/** 状态接口只读取已保存配置；查看页面不会占用任何模板。 */
export async function fetchComicRotationStatus(umo?: string): Promise<ComicTemplateRotationStatus> {
  const response = await apiGet<unknown>("comic/templates/rotation/status", umo ? { group_id: umo.split(":GroupMessage:")[1], umo } : {});
  const data = extractData<unknown>(response);
  const parsed = rotationStatusSchema.safeParse(data);
  if (response?.status !== "error" && parsed.success) return parsed.data;
  const detail = data && typeof data === "object" && "message" in data ? data.message : response?.message;
  throw new Error(typeof detail === "string" ? detail : "未收到有效的漫画模板切换状态");
}

/** 重置所选全局或群进度，不修改用户配置。 */
export async function resetComicRotation(umo?: string): Promise<ComicTemplateRotationStatus> {
  const response = await apiPost<unknown>("comic/templates/rotation/reset", umo ? { action: "reset", group_id: umo.split(":GroupMessage:")[1], umo } : { action: "reset" });
  const data = extractData<unknown>(response);
  const parsed = rotationStatusSchema.safeParse(data);
  if (response?.status !== "error" && parsed.success) return parsed.data;
  const detail = data && typeof data === "object" && "message" in data ? data.message : response?.message;
  throw new Error(typeof detail === "string" ? detail : "无法确认重置结果，请刷新状态核对");
}
