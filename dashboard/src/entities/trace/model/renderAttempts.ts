import { z } from "zod";
import { resolveSpanOutcome } from "./spanOutcome";

// 历史记录可能缺少新字段；单个字段格式异常时，仍展示其他可用信息。
export const renderAttemptSchema = z.object({
  attempt: z.number().int().positive().optional().catch(undefined),
  strategy_name: z.string().optional().catch(undefined),
  priority: z.number().finite().nullable().optional().catch(undefined),
  service_type: z.enum(["astrbot", "custom", "typst"]).optional().catch(undefined),
  font_mode: z.enum(["network", "local"]).optional().catch(undefined),
  resource_environment: z.string().optional().catch(undefined),
  resource_urls: z
    .object({
      cdn_base_url: z.string().optional().catch(undefined),
      google_fonts: z.string().optional().catch(undefined),
      gstatic: z.string().optional().catch(undefined),
    })
    .nullable()
    .optional()
    .catch(undefined),
  render_timeout_ms: z.number().finite().nonnegative().nullable().optional().catch(undefined),
  request_timeout_ms: z.number().finite().nonnegative().nullable().optional().catch(undefined),
  duration_ms: z.number().finite().nonnegative().optional().catch(undefined),
  status: z.string().optional().catch(undefined),
  type: z.string().optional().catch(undefined),
  viewport: z.string().optional().catch(undefined),
  error: z.string().optional().catch(undefined),
  render_service: z
    .object({
      configured_endpoint: z.string().optional().catch(undefined),
      config_lookup: z.string().optional().catch(undefined),
    })
    .optional()
    .catch(undefined),
});

export type RenderAttempt = z.infer<typeof renderAttemptSchema>;

export function getRenderAttemptDiagnostic(payload?: Record<string, unknown>) {
  if (!Array.isArray(payload?.render_attempts)) return null;
  const attempts = payload.render_attempts.map((value) => renderAttemptSchema.safeParse(value));
  const firstFailure = attempts.findIndex(
    (attempt) =>
      attempt.success &&
      resolveSpanOutcome(attempt.data.status ?? "", { error: attempt.data.error }) === "failed",
  );
  if (firstFailure < 0) return null;
  const last = attempts.at(-1);
  const recovered =
    firstFailure < attempts.length - 1 &&
    last?.success === true &&
    resolveSpanOutcome(last.data.status ?? "", { error: last.data.error }) === "success";
  const failed = attempts[firstFailure];
  return {
    recovered,
    label: recovered ? "后续渲染已成功" : "存在失败轮次",
    reason:
      failed.success && failed.data.error
        ? failed.data.error
        : `第 ${firstFailure + 1} 轮渲染失败，未记录具体原因。`,
  };
}
