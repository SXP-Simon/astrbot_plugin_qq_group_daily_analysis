import { expect, it } from "vitest";
import { z } from "zod";
import cases from "../../../../../../tests/fixtures/config_validation_cases.json";
import schema from "../../../../../../_conf_schema.json";
import type { PluginSchema } from "../types";
import { validateConfigWithZod, validateSingleFieldWithZod } from "../validation";

it.each(cases)("与后端共用边界案例：$name", ({ config, valid }) => {
  const before = structuredClone(config);
  const result = validateConfigWithZod(
    z.record(z.string(), z.record(z.string(), z.unknown())).parse(config),
    schema as PluginSchema,
  );
  expect(result.isValid).toBe(valid);
  expect(config).toEqual(before);
  if (!valid) expect(result.errors[0].path).toBeTruthy();
});

it.each([Infinity, -Infinity, NaN])("数值必须有限：%s", (value) => {
  expect(validateSingleFieldWithZod("value", { type: "float" }, value)).toBeTruthy();
});

it("对象字段本身无效时不能被默认子字段掩盖", () => {
  const result = validateConfigWithZod(
    { group: { nested: "wrong" } },
    {
      group: {
        type: "object",
        description: "分组",
        items: {
          nested: { type: "object", items: { child: { type: "int", default: 1 } } },
        },
      },
    },
  );
  expect(result.isValid).toBe(false);
  expect(result.errorMap.group.nested).toContain("JSON 对象");
});

it("隐藏和未启用字段不阻止保存，时间只检查明确声明的字段", () => {
  expect(validateSingleFieldWithZod("runtime_note", { type: "string" }, "elapsed: 2s")).toBeNull();
  const result = validateConfigWithZod(
    { group: { mode: "normal", extra: "wrong" } },
    {
      group: {
        type: "object",
        description: "分组",
        items: {
          mode: { type: "string" },
          extra: { type: "int", condition: { mode: "custom" } },
        },
      },
    },
  );
  expect(result.isValid).toBe(true);
});

it.each([
  { times: ["23:59", " ０:00"] },
  { times: ["24:00"] },
  { times: ["oops"] },
  { times: [1] },
])("定时时间拒绝错误格式 $times", ({ times }) => {
  expect(validateSingleFieldWithZod("auto_analysis_time", { type: "list" }, times)).toBeTruthy();
});

it("定时时间保留空列表关闭语义，接受中文冒号", () => {
  expect(validateSingleFieldWithZod("auto_analysis_time", { type: "list" }, [])).toBeNull();
  expect(validateSingleFieldWithZod("auto_analysis_time", { type: "list" }, ["23：00"])).toBeNull();
});
