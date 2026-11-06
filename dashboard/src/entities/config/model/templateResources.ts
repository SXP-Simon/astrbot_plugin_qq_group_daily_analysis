import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";

export const templateResourceFileSchema = z.object({ name: z.string(), available: z.boolean() });
export const templateResourceStatusSchema: z.ZodType<
  components["schemas"]["TemplateResourceStatus"]
> = z.object({
  directory: z.string(),
  groups: z.array(z.object({ theme: z.string(), files: z.array(templateResourceFileSchema) })),
});

export type TemplateResourceStatus = z.infer<typeof templateResourceStatusSchema>;
