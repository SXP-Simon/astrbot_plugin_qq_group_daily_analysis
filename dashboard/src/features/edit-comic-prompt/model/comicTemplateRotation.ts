import { comicPromptTemplates } from "./useComicPromptEditor";
import type { components } from "../../../shared/api/generated/schema";

export const COMIC_ROTATION_MODES = [
  { value: "fixed", label: "固定模板", description: "沿用提示词设置中选择的默认漫画模板。" },
  { value: "sequential", label: "每次按顺序", description: "每次新生成依次选取候选模板，到末尾后从头开始。" },
  { value: "daily_sequential", label: "每日按顺序", description: "每天按日历推进一个模板，当日保持一致；未生成的日期也会推进。" },
  { value: "random", label: "每次随机", description: "每次新生成独立随机抽取，允许连续选到同一模板。" },
  { value: "daily_random", label: "每日随机", description: "当天首次生成时随机抽取，当日固定；重启后仍沿用当天结果。" },
  { value: "shuffle", label: "洗牌循环", description: "打乱候选模板后逐个使用，全部用完才重新洗牌，避免前后两轮接连重复。" },
] as const;

export type ComicRotationMode = typeof COMIC_ROTATION_MODES[number]["value"];
export type ComicRotationScope = "global" | "group";
export const COMIC_ROTATION_FIELDS = ["comic_template_mode", "comic_template_scope", "comic_template_candidates"];
export const DEFAULT_COMIC_TEMPLATE_CANDIDATES = comicPromptTemplates.map(({ id }) => id);
export const comicTemplateOptions = [
  ...comicPromptTemplates.map(({ id, name }) => ({ value: id, label: name })),
  { value: "custom", label: "自定义提示词" },
];

export type ComicTemplateRotationStatus = components["schemas"]["ComicTemplateRotationStatus"];

export function normalizeComicRotation(value: Record<string, unknown>) {
  const mode = COMIC_ROTATION_MODES.find(({ value: id }) => value.comic_template_mode === id)?.value ?? "fixed";
  const scope: ComicRotationScope = value.comic_template_scope === "group" ? "group" : "global";
  const candidates = Array.isArray(value.comic_template_candidates)
    ? value.comic_template_candidates.filter((id): id is string => typeof id === "string")
    : [...DEFAULT_COMIC_TEMPLATE_CANDIDATES];
  return { mode, scope, candidates };
}

export function isComicGroupUmo(value: string): boolean {
  return /^[^:\s]+:GroupMessage:[^:\s]+$/.test(value);
}
