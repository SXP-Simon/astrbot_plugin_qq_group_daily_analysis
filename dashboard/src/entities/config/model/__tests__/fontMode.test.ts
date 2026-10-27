import { expect, it } from "vitest";
import { renderingSaveSchema, renderingStrategySchema } from "../renderingConfig";

it("旧自定义方案默认在线字体，AstrBot 方案不保留字体模式", () => {
  expect(renderingStrategySchema.parse({ __template_key: "custom" }).font_mode).toBe("network");
  expect(renderingStrategySchema.parse({ __template_key: "strategy", font_mode: "local" })).not.toHaveProperty("font_mode");
});

it.each(["network", "local"])("保存字体模式 %s 时保留未使用的地址和扩展字段", (font_mode) => {
  const draft = { t2i_rendering_strategies: [{ __template_key: "custom", font_mode, google_fonts: "https://saved.example/fonts", gstatic: "https://saved.example/files", future: [1] }] };
  expect(renderingSaveSchema.parse(draft).t2i_rendering_strategies?.[0]).toMatchObject(draft.t2i_rendering_strategies[0]);
});

it.each([null, "", "offline", true, 0, []])("拒绝无效字体模式：%j", (font_mode) => {
  expect(renderingStrategySchema.safeParse({ __template_key: "custom", font_mode }).success).toBe(false);
});
