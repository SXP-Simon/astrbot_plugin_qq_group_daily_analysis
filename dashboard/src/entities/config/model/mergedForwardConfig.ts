import { z } from "zod";

export const mergedForwardEnabledSchema = z.boolean({ error: "合并转发开关必须为布尔值" }).optional();
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
