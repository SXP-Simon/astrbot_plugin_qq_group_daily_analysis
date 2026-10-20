import { z } from "zod";

export const wordCloudOptionsSchema = z.object({
  enabled: z.boolean().default(true),
  send_with_report: z.boolean().default(true),
  template: z.string().default("ATRI"),
  font: z.string().default("wenkai"),
  min_font_size: z.number().int().min(12).max(160).default(34),
  max_font_size: z.number().int().min(12).max(160).default(90),
  max_words: z.number().int().min(1).max(200).default(80),
  word_spacing: z.number().int().min(0).max(40).default(10),
  width: z.number().int().min(800).max(2400).default(1200),
  height: z.number().int().min(600).max(1800).default(900),
  rotation: z.enum(["horizontal", "mixed"]).default("horizontal"),
  palette: z.array(z.string().regex(/^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$/)).max(16).default([]),
  weight_mode: z.enum(["message_count", "occurrence_count"]).default("message_count"),
  min_frequency: z.number().int().min(1).max(10000).default(2),
  min_word_length: z.number().int().min(1).max(20).default(2),
  stopwords: z.array(z.string()).default([]),
  keep_words: z.array(z.string()).default([]),
}).catchall(z.unknown()).refine((value) => value.min_font_size <= value.max_font_size, {
  path: ["min_font_size"], message: "最小字号不能超过最大字号",
});

export type WordCloudOptions = z.infer<typeof wordCloudOptionsSchema>;
export const DEFAULT_WORDCLOUD_OPTIONS = wordCloudOptionsSchema.parse({});

export const wordCloudCatalogSchema = z.object({
  templates: z.array(z.object({ name: z.string(), label: z.string(), defaults: z.record(z.string(), z.unknown()).optional(), thumbnail: z.string().optional() })),
  fonts: z.array(z.object({ id: z.string(), label: z.string(), uploaded: z.boolean().optional() })),
});
export type WordCloudCatalog = z.infer<typeof wordCloudCatalogSchema>;

export const wordCloudSnapshotSchema = z.object({
  id: z.string(), umo: z.string(), group_id: z.string(), group_label: z.string(), date_str: z.string(),
  updated_at: z.number(), message_count: z.number(), word_count: z.number(), start_timestamp: z.number(), end_timestamp: z.number(),
});
export type WordCloudSnapshot = z.infer<typeof wordCloudSnapshotSchema>;
export interface WordCloudPreviewSource { source: "sample" | "snapshot"; snapshot_id?: string; umo?: string }
export const wordCloudMetadataSchema = z.object({
  source: z.enum(["sample", "snapshot"]), snapshot_id: z.string().optional(), umo: z.string().optional(),
  group_id: z.string(), group_label: z.string(), date_str: z.string(), message_count: z.number(), word_count: z.number(),
  eligible_word_count: z.number(), display_word_count: z.number(), start_timestamp: z.number(), end_timestamp: z.number(),
  updated_at: z.number().optional(), notes: z.array(z.string()).optional(),
});

export const wordCloudPreviewSchema = z.object({
  html: z.string().optional(),
  image: z.string().optional(),
  metadata: wordCloudMetadataSchema.optional(),
});
export type WordCloudPreview = z.infer<typeof wordCloudPreviewSchema>;
