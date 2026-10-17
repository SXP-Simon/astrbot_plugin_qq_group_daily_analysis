import { z } from "zod";
import type { SchemaFieldItem, SchemaGroupItem } from "./types";
import { renderingConfigLoadSchema, renderingSaveSchema } from "./renderingConfig";
import { wordCloudOptionsSchema } from "../../wordcloud/model/types";
import { comicRotationConfigSchema, hasEmptyRotatingCustomPrompt } from "./comicRotationConfig";

const schemaField: z.ZodType<SchemaFieldItem> = z.lazy(() => z.object({
  type: z.string(),
  description: z.string().optional(),
  hint: z.string().optional(),
  default: z.unknown().optional(),
  options: z.array(z.union([z.string(), z.number()])).optional(),
  labels: z.array(z.string()).optional(),
  condition: z.record(z.string(), z.unknown()).optional(),
  items: z.union([schemaField, z.record(z.string(), schemaField)]).optional(),
  templates: z.record(z.string(), z.object({
    name: z.string().optional(),
    description: z.string().optional(),
    display_item: z.string().optional(),
    items: z.record(z.string(), schemaField).optional(),
  }).catchall(z.unknown())).optional(),
}).catchall(z.unknown()));

const schemaGroup: z.ZodType<SchemaGroupItem> = z.object({
  description: z.string(),
  type: z.literal("object"),
  hint: z.string().optional(),
  items: z.record(z.string(), schemaField),
}).catchall(z.unknown());

// 未声明的分组及字段原样保留，避免动态表单保存时丢失扩展配置。
export const pluginConfigSchema = z.object({
  t2i_rendering: renderingConfigLoadSchema.optional(),
}).catchall(z.record(z.string(), z.unknown()));

export const pluginConfigResponseSchema = z.object({
  config: pluginConfigSchema,
  schema: z.record(z.string(), schemaGroup),
}).catchall(z.unknown());

export const pluginConfigSaveSchema = pluginConfigSchema.extend({
  t2i_rendering: renderingSaveSchema.optional(),
  wordcloud: wordCloudOptionsSchema.optional(),
  daily_comic: comicRotationConfigSchema.optional(),
}).superRefine((value, context) => {
  if (hasEmptyRotatingCustomPrompt(value.daily_comic, value.prompts)) {
    context.addIssue({ code: "custom", path: ["daily_comic", "comic_template_candidates"], message: "候选包含自定义，请先填写自定义漫画场景分析提示词" });
  }
});
