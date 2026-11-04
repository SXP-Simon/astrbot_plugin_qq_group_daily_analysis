import { z } from "zod";
import type { components, operations } from "../../../shared/api/generated/schema";

export type TypstFontStatus = components["schemas"]["TypstFontStatus"];
export type FontDownloadSource = "cdn" | "github";
export const FONT_DOWNLOAD_SOURCES = [
  { value: "cdn", label: "CDN 优先（大字库直连）" },
  { value: "github", label: "GitHub Raw 直连（全部字体）" },
];
export type FontTransfer = NonNullable<operations["getDownloadProgress"]["responses"][200]["content"]["application/json"]["data"]>;
export const fontTransferSchema: z.ZodType<FontTransfer> = z.object({
  name: z.string(), url: z.string(), received: z.number().nonnegative(), total: z.number().nullable(),
  phase: z.enum(["connecting", "downloading", "validating"]),
  elapsed_seconds: z.number(), idle_seconds: z.number(),
});

export const typstFontStatusSchema: z.ZodType<TypstFontStatus> = z.object({
  directory: z.string(),
  files: z.array(z.string()),
  missing: z.array(z.string()),
  ready: z.boolean(),
  groups: z.array(z.object({
    theme: z.string(), required: z.array(z.string()), missing: z.array(z.string()), ready: z.boolean(),
  })).optional(),
});
