import { z } from "zod";

// 历史提示词和不同分析器的记录并不完整，逐字段保留可以确认的内容。
const promptDetailSchema = z.object({
  prompt: z.string().optional().catch(undefined),
  system_prompt: z.string().optional().catch(undefined),
  completion: z.string().optional().catch(undefined),
  initial_prompt: z.string().optional().catch(undefined),
  initial_completion: z.string().optional().catch(undefined),
  corrected_prompt: z.string().optional().catch(undefined),
  corrected_completion: z.string().optional().catch(undefined),
  provider_id: z.string().optional().catch(undefined),
  model: z.string().optional().catch(undefined),
  provider_type: z.string().optional().catch(undefined),
  tokens: z.number().finite().nonnegative().optional().catch(undefined),
  prompt_tokens: z.number().finite().nonnegative().optional().catch(undefined),
  completion_tokens: z.number().finite().nonnegative().optional().catch(undefined),
  retry_count: z.number().int().nonnegative().optional().catch(undefined),
});

export type PromptDetail = z.infer<typeof promptDetailSchema>;
export interface PromptRecord {
  key: string;
  label: string;
  detail: PromptDetail;
  malformed?: boolean;
}
export interface PromptGroup {
  key: string;
  label: string;
  records: PromptRecord[];
}

const analyzerNames = new Map(
  Object.entries({
    topics: "话题",
    话题分析: "话题",
    话题: "话题",
    user_titles: "用户称号",
    群友画像: "用户称号",
    用户称号: "用户称号",
    golden_quotes: "金句",
    群聊金句: "金句",
    金句: "金句",
    chat_quality: "聊天质量",
    聊天质量: "聊天质量",
    group_sentiment: "情感分析",
    activity_prediction: "活跃预测",
    comic: "群漫画",
    comic_storyboards: "漫画分镜",
    comic_storyboard: "漫画分镜",
    comic_drawing: "生图提示词",
  }),
);

export function getPromptGroups(value: unknown): PromptGroup[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const entries = Object.entries(value).map(([key, raw]) => {
    const parsed = promptDetailSchema.safeParse(typeof raw === "string" ? { prompt: raw } : raw);
    return { key, detail: parsed.success ? parsed.data : {}, malformed: !parsed.success };
  });
  const retryPattern = /^(.*)#(schema_retry|retry)_(\d+)$/;
  const bases = entries.filter(({ key }) => !retryPattern.test(key));
  const groups = new Map<string, PromptGroup>();
  for (const entry of bases) {
    groups.set(entry.key, {
      key: entry.key,
      label: analyzerNames.get(entry.key) ?? entry.key,
      records: [],
    });
  }
  for (const entry of entries) {
    const retry = retryPattern.exec(entry.key);
    if (!retry) continue;
    const baseName = retry[1];
    const aliases = bases.filter(
      ({ key }) => (analyzerNames.get(key) ?? key) === (analyzerNames.get(baseName) ?? baseName),
    );
    // 同名模块有多个来源时不猜测归属；孤立的重试记录仍可单独查看。
    const key = groups.has(baseName) ? baseName : aliases.length === 1 ? aliases[0].key : baseName;
    const group = groups.get(key) ?? { key, label: analyzerNames.get(key) ?? key, records: [] };
    group.records.push({
      ...entry,
      label: `${retry[2] === "schema_retry" ? "格式修复" : "重试"}第 ${Number(retry[3])} 次`,
    });
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    group.records.sort(
      (a, b) => Number(retryPattern.exec(a.key)?.[3]) - Number(retryPattern.exec(b.key)?.[3]),
    );
    const base = bases.find(({ key }) => key === group.key);
    if (!base) continue;
    const detail = base.detail;
    const corrected =
      detail.corrected_prompt !== undefined || detail.corrected_completion !== undefined;
    const initial = detail.initial_prompt !== undefined || detail.initial_completion !== undefined;
    if (initial && (corrected || group.records.length > 0 || (detail.retry_count ?? 0) > 0)) {
      group.records.unshift({
        key: `${base.key}:initial`,
        label: "初始记录",
        // 模块汇总中的模型和 Token 不一定属于首次请求，不挪到初始记录中。
        detail: {
          prompt: detail.initial_prompt,
          completion: detail.initial_completion,
          system_prompt: detail.system_prompt,
        },
      });
    } else if (group.records.length > 0 && !corrected) {
      group.records.unshift({ ...base, label: "模块记录" });
      continue;
    }
    group.records.push({
      ...base,
      label: corrected ? "校正记录" : "模块记录",
      detail: {
        ...detail,
        prompt: detail.corrected_prompt ?? detail.prompt,
        completion: detail.corrected_completion ?? detail.completion,
      },
    });
  }
  return [...groups.values()];
}
