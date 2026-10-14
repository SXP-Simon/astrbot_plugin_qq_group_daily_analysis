import { z } from "zod";
import type { SchemaFieldItem, SchemaGroupItem } from "./types";
import { renderingConfigSchema, renderingSaveSchema } from "./renderingConfig";

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
  t2i_rendering: renderingConfigSchema.optional(),
}).catchall(z.record(z.string(), z.unknown()));

export const pluginConfigResponseSchema = z.object({
  config: pluginConfigSchema,
  schema: z.record(z.string(), schemaGroup),
}).catchall(z.unknown());

export const pluginConfigSaveSchema = pluginConfigSchema.extend({
  t2i_rendering: renderingSaveSchema.optional(),
});
