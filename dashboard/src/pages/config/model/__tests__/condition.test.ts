import { describe, expect, it } from "vitest";
import { isFieldVisible, resolveDependencyValue } from "../useConfigViewModel";
import type { SchemaFieldItem } from "../../../../entities/config/model/types";

const field = (extra: Partial<SchemaFieldItem> = {}) =>
  ({ type: "string", ...extra }) as SchemaFieldItem;

describe("condition 条件显示（官方键）", () => {
  it("未声明 condition 的字段恒显示", () => {
    expect(isFieldVisible(field(), { basic: { report_template: "scrapbook" } })).toBe(true);
  });

  it("单值相等即显示（裸字段名跨分组解析）", () => {
    const item = field({ condition: { report_template: "HatsuneMiku" } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(true);
  });

  it("值不等则隐藏", () => {
    const item = field({ condition: { report_template: "HatsuneMiku" } });
    expect(isFieldVisible(item, { basic: { report_template: "scrapbook" } })).toBe(false);
  });

  it("支持 “分组.字段” 写法", () => {
    const item = field({ condition: { "basic.report_template": "HatsuneMiku" } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(true);
    expect(isFieldVisible(item, { t2i_rendering: {} })).toBe(false);
  });

  it("依赖字段缺失时按未命中处理（隐藏）", () => {
    const item = field({ condition: { report_template: "HatsuneMiku" } });
    expect(isFieldVisible(item, {})).toBe(false);
  });

  it("invisible 优先级高于 condition", () => {
    const item = field({ invisible: true, condition: { report_template: "HatsuneMiku" } });
    expect(isFieldVisible(item, { basic: { report_template: "HatsuneMiku" } })).toBe(false);
  });

  it("多个条件需同时命中（AND）", () => {
    const item = field({
      condition: { report_template: "HatsuneMiku", enable_web_report: true },
    });
    expect(
      isFieldVisible(item, { basic: { report_template: "HatsuneMiku", enable_web_report: true } }),
    ).toBe(true);
    expect(
      isFieldVisible(item, { basic: { report_template: "HatsuneMiku", enable_web_report: false } }),
    ).toBe(false);
  });

  it("按字符串比较：布尔/数字值也能命中", () => {
    const item = field({ condition: { enable_web_report: true } });
    expect(isFieldVisible(item, { basic: { enable_web_report: true } })).toBe(true);
    const numbered = field({ condition: { analysis_days: 3 } });
    expect(isFieldVisible(numbered, { basic: { analysis_days: 3 } })).toBe(true);
    expect(isFieldVisible(numbered, { basic: { analysis_days: 1 } })).toBe(false);
  });

  it("兼容数组写法：命中任一即显示", () => {
    const item = field({ condition: { report_template: ["HatsuneMiku", "ATRI"] } });
    expect(isFieldVisible(item, { basic: { report_template: "ATRI" } })).toBe(true);
    expect(isFieldVisible(item, { basic: { report_template: "scrapbook" } })).toBe(false);
  });

  it("condition 不是对象时按无条件处理（恒显示）", () => {
    const item = field({ condition: null as unknown as Record<string, unknown> });
    expect(isFieldVisible(item, {})).toBe(true);
  });
});

describe("resolveDependencyValue", () => {
  it("优先按“分组.字段”取值", () => {
    expect(resolveDependencyValue({ basic: { report_template: "ATRI" } }, "basic.report_template")).toBe(
      "ATRI",
    );
  });

  it("裸字段名跨分组查找", () => {
    expect(
      resolveDependencyValue({ t2i_rendering: {}, basic: { report_template: "hack" } }, "report_template"),
    ).toBe("hack");
  });

  it("字段不存在时返回 undefined", () => {
    expect(resolveDependencyValue({ basic: {} }, "report_template")).toBeUndefined();
  });
});
