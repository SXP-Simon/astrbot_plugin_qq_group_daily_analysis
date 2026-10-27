import resourceCases from "../../../../../../tests/data/rendering_resources.json";
import serviceCases from "../../../../../../tests/data/rendering_services.json";
import { describe, expect, it } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../configContract";
import { renderingRuntimeSchema, renderingStrategySchema } from "../renderingConfig";
import { validateSingleFieldWithZod } from "../validation";

describe("可扩展渲染方案", () => {
  it("真实配置提供海外优先、内地备用两项默认方案", () => {
    expect(schema.t2i_rendering.items.t2i_rendering_strategies.type).toBe("template_list");
    expect(schema.t2i_rendering.items.t2i_rendering_strategies.templates.strategy.items.priority.default).toBe(10);
    expect(Object.keys(schema.t2i_rendering.items).some((key) => /^t2i_r[12]_/.test(key))).toBe(false);
    expect(schema.t2i_rendering.items).not.toHaveProperty("t2i_font_source");
    expect(schema.t2i_rendering.items.t2i_rendering_strategies.default).toEqual([
      { __template_key: "strategy", name: "海外方案", priority: 10, environment: "Overseas", type: "png", quality: 80, device_scale: "high", timeout: 20000 },
      { __template_key: "mainland", name: "内地方案", priority: 20, environment: "Mainland", type: "png", quality: 80, device_scale: "high", timeout: 20000 },
    ]);
    expect(renderingStrategySchema.parse({}).timeout).toBe(20000);
    expect(schema.t2i_rendering.items).not.toHaveProperty("t2i_cdn_base_url");
    expect(pluginConfigResponseSchema.safeParse({ config: {}, schema }).success).toBe(true);
  });

  it.each([{}, { t2i_rendering_strategies: [] }])("未配置方案时预览使用海外环境，忽略已移除的全局环境 %j", (value) => {
    expect(renderingRuntimeSchema.parse({
      ...value,
      t2i_font_source: "Mainland",
      t2i_mainland_cdn_base_url: "https://mainland.example",
      t2i_overseas_cdn_base_url: "https://overseas.example",
    }).t2i_cdn_base_url).toBe("https://cdn.jsdmirror.com");
  });

  it("预览采用最高优先级方案的环境，且不改变列表顺序", () => {
    const value = {
      t2i_mainland_cdn_base_url: " https://mainland.example/ ",
      t2i_overseas_cdn_base_url: "https://overseas.example",
      t2i_rendering_strategies: [
        { name: "后执行", priority: 20, environment: "Overseas", cdn_base_url: "https://overseas.example" },
        { name: "先执行", priority: 10, environment: "Mainland", cdn_base_url: "https://mainland.example" },
      ],
    };
    const original = structuredClone(value);
    expect(renderingRuntimeSchema.parse(value).t2i_cdn_base_url).toBe("https://mainland.example");
    expect(value).toEqual(original);
    value.t2i_rendering_strategies[0].priority = 5;
    expect(renderingRuntimeSchema.parse(value).t2i_cdn_base_url).toBe("https://overseas.example");
  });

  it("旧环境地址不再影响运行时，每轮缺失地址使用预设", () => {
    expect(renderingRuntimeSchema.parse({
      t2i_cdn_base_url: "https://legacy.example/",
      t2i_mainland_cdn_base_url: "",
      t2i_overseas_cdn_base_url: "https://overseas.example",
      t2i_rendering_strategies: [{ environment: "Mainland" }, { environment: "Overseas" }],
    }).t2i_cdn_base_url).toBe("https://cdn.jsdmirror.com");
  });

  it("保存清除旧环境地址，保留方案和分组的扩展字段", () => {
    const saved = pluginConfigSaveSchema.parse({
      t2i_rendering: {
        t2i_mainland_cdn_base_url: " https://mainland.example/ ",
        t2i_overseas_cdn_base_url: " https://overseas.example/// ",
        t2i_rendering_strategies: [{ __template_key: "strategy", future: [" keep "] }],
        future: { keep: true },
      },
      extra: { untouched: [1] },
    });
    expect(saved.t2i_rendering).not.toHaveProperty("t2i_mainland_cdn_base_url");
    expect(saved.t2i_rendering).not.toHaveProperty("t2i_overseas_cdn_base_url");
    expect(saved.t2i_rendering?.t2i_rendering_strategies?.[0].future).toEqual([" keep "]);
    expect(saved.t2i_rendering?.future).toEqual({ keep: true });
    expect(saved.extra).toEqual({ untouched: [1] });
  });

  it("清空方案后保存明确的默认方案，不改变编辑草稿和扩展字段", () => {
    const draft = { t2i_rendering: { t2i_rendering_strategies: [], future: "保留" } };
    const saved = pluginConfigSaveSchema.parse(draft);
    expect(saved.t2i_rendering?.t2i_rendering_strategies).toEqual(pluginConfigSaveSchema.parse({ t2i_rendering: { t2i_rendering_strategies: schema.t2i_rendering.items.t2i_rendering_strategies.default } }).t2i_rendering?.t2i_rendering_strategies);
    expect(saved.t2i_rendering?.future).toBe("保留");
    expect(draft.t2i_rendering.t2i_rendering_strategies).toEqual([]);
  });

  it.each([
    { priority: true }, { priority: -1 }, { environment: "Local" },
    { type: "gif" }, { quality: 101 }, { timeout: 0 }, { device_scale: "wrong" }, { name: 1 },
  ])("编辑和保存均拒绝无效方案 %j", (value) => {
    expect(renderingStrategySchema.safeParse(value).success).toBe(false);
    expect(validateSingleFieldWithZod("t2i_rendering_strategies", { type: "template_list" }, [value])).toBeTruthy();
    expect(pluginConfigSaveSchema.safeParse({ t2i_rendering: { t2i_rendering_strategies: [value] } }).success).toBe(false);
  });

  it.each(["cdn_base_url", "google_fonts"])("编辑和保存均校验 %s", (key) => {
    expect(validateSingleFieldWithZod(key, { type: "string" }, "https://user:pass@example.com")).toBeTruthy();
    expect(pluginConfigSaveSchema.safeParse({ t2i_rendering: { t2i_rendering_strategies: [{ [key]: "https://user:pass@example.com" }] } }).success).toBe(false);
  });
});


it.each(resourceCases)("前后端共用每轮资源地址边界：%j", ({ plan, expected }) => {
  const input = { t2i_rendering: { t2i_rendering_strategies: [plan] } };
  const before = structuredClone(input);
  const result = pluginConfigSaveSchema.safeParse(input);
  expect(result.success).toBe(expected !== null);
  if (result.success) expect(result.data.t2i_rendering?.t2i_rendering_strategies?.[0]).toMatchObject(expected!);
  expect(input).toEqual(before);
});

it.each(serviceCases)("前后端共用方案类型与旧配置边界：%j", ({ plan, expected }) => {
  const input = { t2i_rendering: { t2i_rendering_strategies: [plan] } };
  const original = structuredClone(input);
  const result = pluginConfigSaveSchema.safeParse(input);
  expect(result.success).toBe(expected !== null);
  if (result.success) expect(result.data.t2i_rendering?.t2i_rendering_strategies?.[0]).toMatchObject(expected!);
  expect(input).toEqual(original);
});

it("自定义方案保存空资源地址，重载后仍可跟随环境且不覆盖手填地址", () => {
  const saved = pluginConfigSaveSchema.parse({ t2i_rendering: { t2i_rendering_strategies: [{
    __template_key: "custom", environment: "Overseas", cdn_base_url: "", google_fonts: "", gstatic: "https://static.example",
  }] } });
  const plan = saved.t2i_rendering!.t2i_rendering_strategies![0];
  expect(plan).toMatchObject({ cdn_base_url: "", google_fonts: "", gstatic: "https://static.example" });
  plan.environment = "Mainland";
  expect(pluginConfigSaveSchema.parse(saved).t2i_rendering?.t2i_rendering_strategies?.[0]).toMatchObject({
    __template_key: "custom", environment: "Mainland", google_fonts: "", gstatic: "https://static.example",
  });
});

it("相同环境的每轮 CDN 独立，预览跟随优先级且保留扩展字段", () => {
  const saved = pluginConfigSaveSchema.parse({ t2i_rendering: {
    t2i_mainland_cdn_base_url: "https://legacy.example",
    t2i_mainland_google_fonts: "https://legacy.example/fonts",
    t2i_rendering_strategies: [
      { environment: "Mainland", priority: 20, cdn_base_url: "https://one.example", future: [1] },
      { environment: "Mainland", priority: 10, cdn_base_url: "https://two.example", google_fonts: "" },
    ],
  } });
  const plans = saved.t2i_rendering!.t2i_rendering_strategies!;
  expect(plans[0].cdn_base_url).toBe("https://two.example");
  expect(plans[0].google_fonts).toBe("https://fonts.loli.net");
  expect(plans[1].future).toEqual([1]);
  expect(plans[1].cdn_base_url).toBe("https://one.example");
  expect(plans[1].google_fonts).toBe("https://fonts.loli.net");
  expect(renderingRuntimeSchema.parse(saved.t2i_rendering).t2i_cdn_base_url).toBe("https://two.example");
});


it("清空方案后，默认方案使用预设字体，不恢复旧全局地址", () => {
  const saved = pluginConfigSaveSchema.parse({ t2i_rendering: {
    t2i_rendering_strategies: [],
    t2i_overseas_google_fonts: " https://legacy.example/fonts/ ",
    t2i_overseas_gstatic: "https://legacy.example/static/",
  } });
  expect(saved.t2i_rendering?.t2i_rendering_strategies?.[0]).toMatchObject({
    google_fonts: "https://fonts.googleapis.com", gstatic: "https://fonts.gstatic.com",
  });
});


it("保存按优先级稳定排序，保留相同优先级、扩展字段和原草稿", () => {
  const draft = { t2i_rendering: { t2i_rendering_strategies: [
    { name: "后执行", priority: 30, future: { keep: true } },
    { name: "同级甲", priority: 10 },
    { name: "同级乙", priority: 10 },
  ] } };
  const before = structuredClone(draft);
  const result = pluginConfigSaveSchema.parse(draft);
  expect(result.t2i_rendering?.t2i_rendering_strategies?.map((plan) => plan.name)).toEqual(["同级甲", "同级乙", "后执行"]);
  expect(result.t2i_rendering?.t2i_rendering_strategies?.[2].future).toEqual({ keep: true });
  expect(draft).toEqual(before);
});
