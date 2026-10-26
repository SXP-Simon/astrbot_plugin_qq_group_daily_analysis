import { describe, expect, it } from "vitest";
import cases from "../../../../../../tests/fixtures/cdn_url_cases.json";
import schema from "../../../../../../_conf_schema.json";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../configContract";
import { cdnBaseUrlSchema, DEFAULT_TEMPLATE_CDN_BASE_URL, renderingRuntimeSchema } from "../renderingConfig";
import { validateSingleFieldWithZod } from "../validation";

describe("CDN 前后端共享边界", () => {
  it.each(cases)("$input → $normalized", ({ input, normalized }) => {
    const result = cdnBaseUrlSchema.safeParse(input);
    expect(result.success).toBe(normalized !== null);
    if (result.success) expect(result.data).toBe(normalized);
    const runtime = renderingRuntimeSchema.safeParse({ t2i_rendering_strategies: [{ cdn_base_url: input }] });
    expect(runtime.success).toBe(normalized !== null);
    if (runtime.success) expect(runtime.data.t2i_cdn_base_url).toBe(normalized || DEFAULT_TEMPLATE_CDN_BASE_URL);
  });

  it("拒绝过长地址，编辑提示与保存一致", () => {
    expect(cdnBaseUrlSchema.safeParse("https://" + "a".repeat(2048)).success).toBe(false);
    expect(validateSingleFieldWithZod("cdn_base_url", { type: "string" }, "https://example.com/npm")).toBeTruthy();
    expect(renderingRuntimeSchema.parse({}).t2i_cdn_base_url).toBe(DEFAULT_TEMPLATE_CDN_BASE_URL);
    expect(schema.t2i_rendering.items).not.toHaveProperty("t2i_cdn_base_url");
  });
});

describe("配置响应契约", () => {
  it("真实 Schema 可解析且动态字段读取、保存不丢失", () => {
    const config = {
      t2i_rendering: { t2i_cdn_base_url: " https://fastly.jsdelivr.net/ ", future: { list: [{ id: 1 }] } },
      future_group: { unknown: [null, false, { extra: " untouched " }] },
      data: { nested: "保留名为 data 的配置分组" },
    };
    const response = pluginConfigResponseSchema.parse({ config, schema });
    expect(response).toEqual({ config, schema });
    const saved = pluginConfigSaveSchema.parse(response.config);
    expect(saved).toEqual({ ...config, t2i_rendering: { future: config.t2i_rendering.future } });
    expect(config.t2i_rendering.t2i_cdn_base_url).toBe(" https://fastly.jsdelivr.net/ ");
  });

  it.each([
    null, {}, { config: {} }, { config: [], schema: {} },
    { config: { t2i_rendering: [] }, schema: {} },
    { config: {}, schema: { basic: { type: "object", description: "基础", items: { enabled: {} } } } },
  ])("拒绝错误响应结构：%j", (response) => {
    expect(pluginConfigResponseSchema.safeParse(response).success).toBe(false);
  });

  it.each(["wrong", 123, null, false, [], { invalid: true }])("旧的错误值 %j 允许加载修正，但不能重新保存", (value) => {
    const config = { t2i_rendering: { t2i_rendering_strategies: [{ cdn_base_url: value }], extra: "保留" } };
    expect(pluginConfigResponseSchema.parse({ config, schema: {} }).config).toEqual(config);
    expect(pluginConfigSaveSchema.safeParse(config).success).toBe(false);
    const repaired = { ...config, t2i_rendering: { ...config.t2i_rendering, t2i_rendering_strategies: [{ cdn_base_url: " https://fastly.jsdelivr.net/ " }] } };
    const saved = pluginConfigSaveSchema.parse(repaired).t2i_rendering;
    expect(saved?.t2i_rendering_strategies?.[0].cdn_base_url).toBe("https://fastly.jsdelivr.net");
    expect(saved?.extra).toBe("保留");
  });
});
