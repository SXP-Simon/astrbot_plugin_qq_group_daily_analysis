import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";

export type TypstFontStatus = components["schemas"]["TypstFontStatus"];

export const typstFontStatusSchema: z.ZodType<TypstFontStatus> = z.object({
  directory: z.string(),
  files: z.array(z.string()),
  missing: z.array(z.string()),
  ready: z.boolean(),
  groups: z.array(z.object({
    theme: z.string(), required: z.array(z.string()), missing: z.array(z.string()), ready: z.boolean(),
  })).optional(),
});
