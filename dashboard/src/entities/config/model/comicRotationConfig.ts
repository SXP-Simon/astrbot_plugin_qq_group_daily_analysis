import { z } from "zod";
import catalog from "../../../../../src/shared/comic_prompt_templates.json";

const validTemplates = new Set([...Object.keys(catalog), "custom"]);
const candidateList = z.array(z.string()).superRefine((ids, context) => {
  if (ids.some((id) => !validTemplates.has(id))) context.addIssue({ code: "custom", message: "候选中包含未知的漫画模板" });
  if (new Set(ids).size !== ids.length) context.addIssue({ code: "custom", message: "漫画候选模板不能重复" });
});

/** 兼容缺少新增字段的旧配置；明确配置的无效值必须在保存前修复。 */
export const comicRotationConfigSchema = z.object({
  comic_template_mode: z.enum(["fixed", "sequential", "daily_sequential", "random", "daily_random", "shuffle"], { error: "请选择有效的漫画模板切换模式" }).optional(),
  comic_template_scope: z.enum(["global", "group"], { error: "请选择全局共享或按群独立" }).optional(),
  comic_template_candidates: candidateList.optional(),
}).catchall(z.unknown()).superRefine((value, context) => {
  if (value.comic_template_mode && value.comic_template_mode !== "fixed" && value.comic_template_candidates?.length === 0) {
    context.addIssue({ code: "custom", path: ["comic_template_candidates"], message: "自动切换至少需要一个候选模板" });
  }
});

/** 自定义候选需要有实际文本，避免运行时悄悄退回经典风格。 */
export function hasEmptyRotatingCustomPrompt(dailyComic: Record<string, unknown> | undefined, prompts: Record<string, unknown> | undefined): boolean {
  if (!dailyComic || !dailyComic.comic_template_mode || dailyComic.comic_template_mode === "fixed") return false;
  if (!Array.isArray(dailyComic.comic_template_candidates) || !dailyComic.comic_template_candidates.includes("custom")) return false;
  const comic = prompts?.comic_analysis_prompts;
  const custom = comic && typeof comic === "object" && "comic_storyboard_prompt" in comic ? comic.comic_storyboard_prompt : undefined;
  return typeof custom !== "string" || !custom.trim();
}
