import { expect, it } from "vitest";
import { validateSingleFieldWithZod } from "@/entities/config/model/validation";

it("对象编辑保留不完整草稿时阻止保存，完整对象与可选空值继续有效", () => {
  const field = { type: "object" };
  expect(validateSingleFieldWithZod("extension", field, '{"value":')).toContain("JSON 对象");
  expect(validateSingleFieldWithZod("extension", field, [1, 2])).toContain("JSON 对象");
  expect(validateSingleFieldWithZod("extension", field, { value: 1 })).toBeNull();
  expect(validateSingleFieldWithZod("extension", field, null)).toBeNull();
});
