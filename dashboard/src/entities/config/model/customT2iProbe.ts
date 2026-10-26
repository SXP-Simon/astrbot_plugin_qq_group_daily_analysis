import { z } from "zod";
import type { components } from "../../../shared/api/generated/schema";
import { DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS, renderingStrategySchema } from "./renderingConfig";

export type CustomT2iProbe = components["schemas"]["CustomT2iProbe"];
export type CustomT2iProbeRequest = components["schemas"]["CustomT2iProbeRequest"];

// 表单草稿可能尚未完成，校验时复用实际保存的配置规则。
export interface CustomT2iProbeInput {
  service_endpoint?: unknown;
  service_token?: unknown;
  timeout?: unknown;
  request_timeout?: unknown;
}

export const customT2iProbeRequestSchema = renderingStrategySchema.transform((plan): CustomT2iProbeRequest => ({
  service_endpoint: plan.service_endpoint,
  service_token: plan.service_token,
  timeout: plan.timeout,
  request_timeout: plan.request_timeout ?? DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS,
}));

export const customT2iProbeSchema: z.ZodType<CustomT2iProbe> = z.object({
  image_data_url: z.string().regex(/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/),
  elapsed_ms: z.number().finite().nonnegative(),
});
