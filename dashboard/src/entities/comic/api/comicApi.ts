import { z } from "zod";
import { apiGet, apiPost, extractData } from "@/shared/api/bridge";
import type { components, paths } from "@/shared/api/generated/schema";

export type ComicRotationEntry = components["schemas"]["ComicRotationEntry"];
export type ComicRotationScope =
  paths["/config/comic-rotation/reset"]["post"]["requestBody"]["content"]["application/json"];
export type ComicPreviewRequest =
  paths["/plugin-data/comic-previews/refresh"]["post"]["requestBody"]["content"]["application/json"];

const rotationEntry: z.ZodType<ComicRotationEntry> = z.object({
  platform_id: z.string().nullable(),
  group_id: z.string().nullable(),
  last_style_name: z.string(),
  last_style_number: z.number().int().positive(),
  selected_date: z.string(),
});
const successSchema = z.object({ success: z.literal(true) });

export async function fetchComicRotation() {
  const response = await apiGet("config/comic-rotation");
  const result = z.object({ items: z.array(rotationEntry) }).safeParse(extractData(response));
  if (!result.success) throw new Error(response?.message || "读取漫画轮换进度失败");
  return result.data.items;
}

export async function resetComicRotation(scope: ComicRotationScope) {
  const response = await apiPost("config/comic-rotation/reset", scope);
  if (!successSchema.safeParse(extractData(response)).success)
    throw new Error(response?.message || "重置轮换进度失败");
}

export async function refreshComicPreview(input: ComicPreviewRequest) {
  const response = await apiPost("plugin-data/comic-previews/refresh", input);
  if (!successSchema.safeParse(extractData(response)).success)
    throw new Error(response?.message || "重新获取漫画样图失败");
}
