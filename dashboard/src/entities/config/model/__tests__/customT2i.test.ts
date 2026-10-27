import { expect, it } from "vitest";
import cases from "../../../../../../tests/data/t2i_endpoints.json";
import { renderingStrategySchema, t2iEndpointSchema } from "../renderingConfig";
import { pluginConfigSaveSchema } from "../configContract";

it.each(cases.valid)("服务地址 %s 与后端一致规范化为 %s", (input, expected) => {
  expect(t2iEndpointSchema.parse(input)).toBe(expected);
  expect(renderingStrategySchema.parse({ render_service: "custom", service_endpoint: input }).service_endpoint).toBe(expected);
});

it.each(cases.invalid)("拒绝自定义服务地址 %j", (input) => {
  expect(t2iEndpointSchema.safeParse(input).success).toBe(false);
  expect(renderingStrategySchema.safeParse({ render_service: "custom", service_endpoint: input }).success).toBe(false);
});

it("旧方案默认跟随 AstrBot，未启用的地址草稿不影响保存", () => {
  const result = renderingStrategySchema.parse({ service_endpoint: "还没填写完整" });
  expect(result.__template_key).toBe("strategy");
  expect(result).not.toHaveProperty("render_service");
  expect(result.service_token).toBe("");
  expect(result.service_endpoint).toBe("还没填写完整");
});

it.each([{ render_service: "local" }, { service_endpoint: 1 }, { service_token: 1 }, { service_token: "secret\r\nInjected: yes" }, { service_token: "密钥" }])("拒绝无效服务字段 %j", (value) => {
  expect(renderingStrategySchema.safeParse(value).success).toBe(false);
});

it("保存服务地址和 Token 时整理空白并保留其他扩展字段", () => {
  const original = { t2i_rendering: { t2i_rendering_strategies: [{ __template_key: "strategy", render_service: "custom", service_endpoint: " http://127.0.0.1:8999/text2img/generate/ ", service_token: " secret ", future: [1] }] } };
  const saved = pluginConfigSaveSchema.parse(original);
  expect(saved.t2i_rendering?.t2i_rendering_strategies?.[0]).toMatchObject({ service_endpoint: "http://127.0.0.1:8999/text2img", service_token: "secret", future: [1] });
  expect(saved.t2i_rendering?.t2i_rendering_strategies?.[0]).not.toHaveProperty("render_service");
  expect(original.t2i_rendering.t2i_rendering_strategies[0].service_token).toBe(" secret ");
});
