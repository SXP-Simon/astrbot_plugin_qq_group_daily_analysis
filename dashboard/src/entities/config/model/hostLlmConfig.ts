import { z } from "zod";
import type { components } from "@/shared/api/generated/schema";

export type HostLlmConfig = components["schemas"]["HostLlmConfig"];
export type HostLlmProvider = components["schemas"]["HostLlmProvider"];

export const hostLlmConfigSchema: z.ZodType<HostLlmConfig> = z.object({
  primary_id: z.string().nullable(),
  fallback_ids: z.array(z.string()),
  providers: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      model: z.string(),
      available: z.boolean(),
    }),
  ),
});

const tasks = [
  ["默认分析", ""],
  ["话题分析", "topic_provider_id"],
  ["用户称号", "user_title_provider_id"],
  ["群聊金句", "golden_quote_provider_id"],
  ["聊天质量", "quality_provider_id"],
  ["漫画分镜", "drawing_prompt_provider_id"],
] as const;

export function describeLlmChains(host: HostLlmConfig, draft: Record<string, unknown>) {
  const mainId = typeof draft.llm_provider_id === "string" ? draft.llm_provider_id.trim() : "";
  const available = new Map(
    host.providers.filter((item) => item.available).map((item) => [item.id, item]),
  );
  const defaultId =
    (mainId && available.has(mainId) ? mainId : null) ??
    (host.primary_id && available.has(host.primary_id) ? host.primary_id : null) ??
    host.providers.find((item) => item.available)?.id;
  const inherit = !mainId;
  const rows = tasks.map(([label, key]) => {
    const value = draft[key];
    const specificId = key && typeof value === "string" ? value.trim() : "";
    const ids = [
      ...new Set([
        ...(specificId && available.has(specificId) ? [specificId] : []),
        ...(defaultId ? [defaultId] : []),
        ...(inherit ? host.fallback_ids : []),
      ]),
    ];
    const models = ids.flatMap((id) => {
      const item = available.get(id);
      return item ? [item] : [];
    });
    const missing = [specificId, mainId].filter((id) => id && !available.has(id));
    return { label, models, missing: [...new Set(missing)] };
  });
  return { inherit, rows };
}
