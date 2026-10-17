import { describe, expect, it } from "vitest";
import { mergedForwardConfigSchema } from "../mergedForwardConfig";
import { validateConfigWithZod, validateSingleFieldWithZod } from "../validation";
import type { PluginSchema } from "../types";

const schema: PluginSchema = { basic: { type: "object", description: "基础设置", items: {
  enable_merged_forward: { type: "bool", default: false },
  merged_forward_timeout: { type: "int", default: 600, min: 10, max: 3600 },
} } };

describe("合并转发严格配置契约", () => {
  it("兼容旧配置并保留基础设置中的其他字段", () => {
    const legacy = { show_report_caption: false, future: [" unchanged "] };
    expect(mergedForwardConfigSchema.parse(legacy)).toEqual(legacy);
    expect(validateConfigWithZod({}, schema).isValid).toBe(true);
    expect(validateConfigWithZod({ basic: legacy }, schema).isValid).toBe(true);
  });

  it.each([false, true])("实际布尔开关 %s 可保存", (enabled) => {
    const config = { basic: { enable_merged_forward: enabled } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(true);
    expect(validateConfigWithZod(config, schema).isValid).toBe(true);
  });

  it.each(["false", "true", 0, 1, null, [], {}])("开关拒绝隐式类型转换：%j", (enabled) => {
    const config = { basic: { enable_merged_forward: enabled } };
    expect(mergedForwardConfigSchema.safeParse(config.basic).success).toBe(false);
    const result = validateConfigWithZod(config, schema);
    expect(result.errorMap.basic.enable_merged_forward).toContain("布尔");
    expect(result.groupErrorCounts.basic).toBe(1);
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
    const field = { type: "bool" };
    expect(validateSingleFieldWithZod("enable_merged_forward", field, "false", "basic")).toBeTruthy();
    expect(validateSingleFieldWithZod("enable_merged_forward", field, "false", "future")).toBeNull();
  });
});
