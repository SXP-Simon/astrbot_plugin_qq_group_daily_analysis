import { z } from "zod";

export const mergedForwardEnabledSchema = z.array(
  z.enum(["report", "wordcloud", "comic"], { error: "请选择分析报告、词云或漫画" }),
  { error: "合并转发内容必须为多选列表" },
).refine((items) => new Set(items).size === items.length, "合并转发内容不能重复选择").optional();
export const mergedForwardTimeoutSchema = z.number({ error: "合并转发等待超时必须为 10–3600 秒的整数" })
  .int("合并转发等待超时必须为 10–3600 秒的整数")
  .min(10, "合并转发等待超时不能小于 10 秒")
  .max(3600, "合并转发等待超时不能大于 3600 秒")
  .optional();

/** 缺少新字段的旧基础配置保持原样，显式提供的值不做隐式转换。 */
export const mergedForwardConfigSchema = z.object({
  enable_merged_forward: mergedForwardEnabledSchema,
  merged_forward_timeout: mergedForwardTimeoutSchema,
}).catchall(z.unknown());

/** 仅在读取旧配置时迁移布尔开关，损坏值保留给表单提示和修正。 */
export const mergedForwardConfigLoadSchema = z.object({
  enable_merged_forward: z.unknown().transform((value) =>
    value === true ? ["report", "wordcloud", "comic"] : value === false ? [] : value,
  ).optional(),
}).catchall(z.unknown());
