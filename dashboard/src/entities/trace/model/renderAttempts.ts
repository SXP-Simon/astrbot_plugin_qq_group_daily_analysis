import { z } from "zod";

// 历史记录可能缺少新字段；单个字段格式异常时，仍展示其他可用信息。
export const renderAttemptSchema = z.object({
  attempt: z.number().optional().catch(undefined),
  strategy_name: z.string().optional().catch(undefined),
  priority: z.number().nullable().optional().catch(undefined),
  service_type: z.enum(["astrbot", "custom"]).optional().catch(undefined),
  font_mode: z.enum(["network", "local"]).optional().catch(undefined),
  resource_environment: z.string().optional().catch(undefined),
  resource_urls: z.object({
    cdn_base_url: z.string().optional().catch(undefined),
    google_fonts: z.string().optional().catch(undefined),
    gstatic: z.string().optional().catch(undefined),
  }).nullable().optional().catch(undefined),
  render_timeout_ms: z.number().nullable().optional().catch(undefined),
  request_timeout_ms: z.number().nullable().optional().catch(undefined),
  duration_ms: z.number().optional().catch(undefined),
  status: z.string().optional().catch(undefined),
  type: z.string().optional().catch(undefined),
  viewport: z.string().optional().catch(undefined),
  error: z.string().optional().catch(undefined),
  render_service: z.object({
    configured_endpoint: z.string().optional().catch(undefined),
    config_lookup: z.string().optional().catch(undefined),
  }).optional().catch(undefined),
});

export type RenderAttempt = z.infer<typeof renderAttemptSchema>;
