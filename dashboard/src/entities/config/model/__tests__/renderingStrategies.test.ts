import { describe, expect, it } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../configContract";
import { renderingRuntimeSchema, renderingStrategySchema } from "../renderingConfig";
import { validateSingleFieldWithZod } from "../validation";

describe("可扩展渲染方案", () => {
  it("真实配置使用方案模板，旧参数仅用于兼容", () => {
    expect(schema.t2i_rendering.items.t2i_rendering_strategies.type).toBe("template_list");
    expect(schema.t2i_rendering.items.t2i_rendering_strategies.templates.strategy.items.priority.default).toBe(10);
    expect(schema.t2i_rendering.items.t2i_font_source.invisible).toBe(true);
    expect(schema.t2i_rendering.items.t2i_cdn_base_url.invisible).toBe(true);
    expect(pluginConfigResponseSchema.safeParse({ config: {}, schema }).success).toBe(true);
  });

  it("预览采用最高优先级方案的环境，且不改变列表顺序", () => {
    const value = {
      t2i_mainland_cdn_base_url: " https://mainland.example/ ",
      t2i_overseas_cdn_base_url: "https://overseas.example",
      t2i_rendering_strategies: [
        { name: "后执行", priority: 20, environment: "Overseas" },
        { name: "先执行", priority: 10, environment: "Mainland" },
      ],
    };
    const original = structuredClone(value);
    expect(renderingRuntimeSchema.parse(value).t2i_cdn_base_url).toBe("https://mainland.example");
    expect(value).toEqual(original);
    value.t2i_rendering_strategies[0].priority = 5;
    expect(renderingRuntimeSchema.parse(value).t2i_cdn_base_url).toBe("https://overseas.example");
  });

  it("相同优先级保持列表顺序，空环境地址沿用旧配置", () => {
    expect(renderingRuntimeSchema.parse({
      t2i_cdn_base_url: "https://legacy.example/",
      t2i_mainland_cdn_base_url: "",
      t2i_overseas_cdn_base_url: "https://overseas.example",
      t2i_rendering_strategies: [{ environment: "Mainland" }, { environment: "Overseas" }],
    }).t2i_cdn_base_url).toBe("https://legacy.example");
  });

  it("保存规范化环境地址，保留方案和分组的扩展字段", () => {
    const saved = pluginConfigSaveSchema.parse({
      t2i_rendering: {
        t2i_mainland_cdn_base_url: " https://mainland.example/ ",
        t2i_overseas_cdn_base_url: " https://overseas.example/// ",
        t2i_rendering_strategies: [{ __template_key: "strategy", future: [" keep "] }],
        future: { keep: true },
      },
      extra: { untouched: [1] },
    });
    expect(saved.t2i_rendering?.t2i_mainland_cdn_base_url).toBe("https://mainland.example");
    expect(saved.t2i_rendering?.t2i_overseas_cdn_base_url).toBe("https://overseas.example");
    expect(saved.t2i_rendering?.t2i_rendering_strategies?.[0].future).toEqual([" keep "]);
    expect(saved.t2i_rendering?.future).toEqual({ keep: true });
    expect(saved.extra).toEqual({ untouched: [1] });
  });

  it.each([
    { priority: true }, { priority: -1 }, { environment: "Local" },
    { type: "gif" }, { quality: 101 }, { timeout: 0 }, { device_scale: "wrong" }, { name: 1 },
  ])("编辑和保存均拒绝无效方案 %j", (value) => {
    expect(renderingStrategySchema.safeParse(value).success).toBe(false);
    expect(validateSingleFieldWithZod("t2i_rendering_strategies", { type: "template_list" }, [value])).toBeTruthy();
    expect(pluginConfigSaveSchema.safeParse({ t2i_rendering: { t2i_rendering_strategies: [value] } }).success).toBe(false);
  });

  it.each(["t2i_mainland_cdn_base_url", "t2i_overseas_cdn_base_url"])("编辑和保存均校验 %s", (key) => {
    expect(validateSingleFieldWithZod(key, { type: "string" }, "https://example.com/gh/file")).toBeTruthy();
    expect(pluginConfigSaveSchema.safeParse({ t2i_rendering: { [key]: "https://user:pass@example.com" } }).success).toBe(false);
  });
});
