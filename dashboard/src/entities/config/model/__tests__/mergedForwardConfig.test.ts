import { describe, expect, it } from "vitest";
import { mergedForwardConfigSchema } from "../mergedForwardConfig";
import { validateConfigWithZod, validateSingleFieldWithZod } from "../validation";
import type { PluginSchema } from "../types";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../configContract";

const schema: PluginSchema = { basic: { type: "object", description: "基础设置", items: {
  enable_merged_forward: { type: "list", default: [], options: ["report", "wordcloud", "comic"], labels: ["分析报告", "词云", "漫画"] },
  merged_forward_timeout: { type: "int", default: 600, min: 10, max: 3600 },
} } };

describe("合并转发严格配置契约", () => {
  it("兼容旧配置并保留基础设置中的其他字段", () => {
    const legacy = { show_report_caption: false, future: [" unchanged "] };
    expect(mergedForwardConfigSchema.parse(legacy)).toEqual(legacy);
    expect(validateConfigWithZod({}, schema).isValid).toBe(true);
    expect(validateConfigWithZod({ basic: legacy }, schema).isValid).toBe(true);
  });

  it.each([[], ["report"], ["wordcloud", "comic"], ["comic", "report", "wordcloud"]].map((items) => ({ items })))("空选、部分及全选 $items 可保存且保持顺序", ({ items }) => {
    const config = { basic: { enable_merged_forward: items } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(true);
    expect(validateConfigWithZod(config, schema).isValid).toBe(true);
    expect(pluginConfigSaveSchema.parse(config)).toEqual(config);
  });

  it.each(["false", "true", true, false, 0, 1, null, {}, ["unknown"], ["Report"], [1], ["report", "report"]].map((enabled) => ({ enabled })))("多选拒绝错误类型、无效值及重复值：$enabled", ({ enabled }) => {
    const config = { basic: { enable_merged_forward: enabled } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(false);
    expect(pluginConfigSaveSchema.safeParse(config).success).toBe(false);
    const result = validateConfigWithZod(config, schema);
    expect(result.errorMap.basic.enable_merged_forward).toBeTruthy();
    expect(result.groupErrorCounts.basic).toBe(1);
  });

  it.each([true, false])("旧布尔开关 %s 读取时迁移，保存为明确的多选列表", (enabled) => {
    const config = { basic: { enable_merged_forward: enabled, show_report_caption: false } };
    const response = pluginConfigResponseSchema.parse({ config, schema });
    const expected = { basic: { ...config.basic, enable_merged_forward: enabled ? ["report", "wordcloud", "comic"] : [] } };
    expect(response.config).toEqual(expected);
    expect(pluginConfigSaveSchema.parse(response.config)).toEqual(expected);
    expect(config.basic.enable_merged_forward).toBe(enabled);
  });

  it.each([10, 11, 600, 3599, 3600])("范围内整数超时 %s 可保存", (timeout) => {
    const config = { basic: { merged_forward_timeout: timeout } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(true);
    expect(validateConfigWithZod(config, schema).isValid).toBe(true);
  });

  it.each([0, 9, 3601, "600", 600.5, true, false, null, [], {}, Infinity, NaN])("超时拒绝错误类型及越界值：%j", (timeout) => {
    const config = { basic: { merged_forward_timeout: timeout } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(false);
    const result = validateConfigWithZod(config, schema);
    expect(result.errorMap.basic.merged_forward_timeout).toBeTruthy();
    expect(result.errors[0].domId).toBe("cfg-field-basic-merged_forward_timeout");
  });

  it.each([null, [], "invalid", true, 0])("损坏的基础分组被拒绝：%j", (basic) => {
    expect(mergedForwardConfigSchema.safeParse(basic).success).toBe(false);
    const malformed = { basic } as unknown as Record<string, Record<string, unknown>>;
    const result = validateConfigWithZod(malformed, schema);
    expect(result.isValid).toBe(false);
    expect(result.errorMap.basic.enable_merged_forward).toContain("必须是对象");
  });

  it("单字段即时校验使用严格规则，不影响其他分组同名字段", () => {
    const field = { type: "list" };
    expect(validateSingleFieldWithZod("enable_merged_forward", field, ["report", "report"], "basic")).toBeTruthy();
    expect(validateSingleFieldWithZod("enable_merged_forward", field, ["report", "report"], "future")).toBeNull();
  });
});
