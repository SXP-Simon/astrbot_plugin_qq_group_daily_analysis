import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";
import { DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS, renderingStrategySchema } from "./renderingConfig";

export type T2iProbe = components["schemas"]["T2iProbe"];
export type T2iProbeRequest = components["schemas"]["T2iProbeRequest"];

// 表单草稿可能尚未完成，校验时复用实际保存的配置规则。
export interface T2iProbeInput {
  render_service?: unknown;
  service_endpoint?: unknown;
  service_token?: unknown;
  timeout?: unknown;
  request_timeout?: unknown;
  group_id?: unknown;
  platform_id?: unknown;
}

const targetSchema = z.object({
  group_id: z.string().max(256).regex(/^[^\s\p{C}]*$/u).optional(),
  platform_id: z.string().max(256).regex(/^[^\s\p{C}]*$/u).optional(),
}).refine((value) => Boolean(value.group_id) === Boolean(value.platform_id), "请选择完整的群聊和平台");

export const t2iProbeRequestSchema = renderingStrategySchema.and(targetSchema)
  .transform((plan): T2iProbeRequest => plan.__template_key === "custom" ? {
    render_service: "custom",
    service_endpoint: plan.service_endpoint,
    service_token: plan.service_token,
    timeout: plan.timeout,
    request_timeout: plan.request_timeout ?? DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS,
  } : {
    render_service: "astrbot",
    timeout: plan.timeout,
    ...(plan.group_id ? { group_id: plan.group_id, platform_id: plan.platform_id } : {}),
  });

export const t2iProbeSchema: z.ZodType<T2iProbe> = z.object({
  image_data_url: z.string().regex(/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/),
  elapsed_ms: z.number().finite().nonnegative(),
});
