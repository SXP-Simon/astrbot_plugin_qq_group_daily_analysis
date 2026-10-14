import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";

export type TemplateCdnProbe = components["schemas"]["TemplateCdnProbe"];
export type TemplateCdnProbeRequest = components["schemas"]["TemplateCdnProbeRequest"];

export const templateCdnProbeSchema: z.ZodType<TemplateCdnProbe> = z.object({
  base_url: z.string(),
  usable: z.boolean(),
  checks: z.array(z.object({
    id: z.string().min(1),
    label: z.string().min(1),
    description: z.string(),
    kind: z.enum(["gh", "npm"]),
    url: z.string(),
    success: z.boolean(),
    status_code: z.number().int().nullable(),
    elapsed_ms: z.number().nonnegative(),
    error: z.string().nullable(),
  })).min(2),
}).refine(
  (result) => new Set(result.checks.map((check) => check.id)).size === result.checks.length &&
    new Set(result.checks.map((check) => check.kind)).size === 2 &&
    result.usable === result.checks.every((check) => check.success),
  "CDN 检测汇总与单项结果不一致",
);
