import { z } from "zod";

export const llmAttemptSchema = z.object({
  area: z.string().optional().catch(undefined),
  provider_id: z.string().optional().catch(undefined),
  model: z.string().optional().catch(undefined),
  status: z.string().optional().catch(undefined),
  error: z.string().optional().catch(undefined),
  skip_reason: z.string().optional().catch(undefined),
  attempt: z.number().int().positive().optional().catch(undefined),
  duration_ms: z.number().nonnegative().optional().catch(undefined),
  is_fallback: z.boolean().optional().catch(undefined),
});
