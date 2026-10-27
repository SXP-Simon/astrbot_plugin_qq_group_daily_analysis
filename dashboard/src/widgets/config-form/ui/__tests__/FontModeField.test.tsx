import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

function ConfigField({ kind = "custom" }: { kind?: "custom" | "strategy" | "mainland" }) {
  // 不含新字段的旧条目，仍应默认显示在线字体的地址。
  const [value, setValue] = useState<unknown>([{ __template_key: kind, google_fonts: "https://saved.example/fonts", gstatic: "https://saved.example/files" }]);
  return <>
    <FieldRenderer fieldKey="t2i_rendering_strategies" fieldSchema={schema.t2i_rendering.items.t2i_rendering_strategies} value={value} onChange={setValue} />
    <output data-testid="draft">{JSON.stringify(value)}</output>
  </>;
}

it("旧自定义条目默认在线；切换后隐藏字体地址，切回保留输入，CDN 始终可用", () => {
  render(<ConfigField />);
  expect(screen.getByRole("combobox", { name: "Google Fonts 地址" })).toHaveValue("https://saved.example/fonts");
  expect(screen.getByRole("combobox", { name: "字体文件地址（Gstatic）" })).toHaveValue("https://saved.example/files");
  expect(screen.getByRole("link", { name: "安装方法和模板字体清单" })).toHaveAttribute("href", expect.stringContaining("docs/T2I_FONTS.md"));
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "字体加载方式" }));
  fireEvent.click(screen.getByText("使用已安装字体", { exact: true }));
  expect(screen.queryByRole("combobox", { name: "Google Fonts 地址" })).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "字体文件地址（Gstatic）" })).not.toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "模板资源 CDN" })).toBeInTheDocument();
  expect(JSON.parse(screen.getByTestId("draft").textContent || "[]")[0]).toMatchObject({ font_mode: "local", google_fonts: "https://saved.example/fonts", gstatic: "https://saved.example/files" });
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "字体加载方式" }));
  fireEvent.click(screen.getByText("在线字体（默认）", { exact: true }));
  expect(screen.getByRole("combobox", { name: "Google Fonts 地址" })).toHaveValue("https://saved.example/fonts");
}, 20000);

it.each(["strategy", "mainland"] as const)("%s 方案不提供字体模式", (kind) => {
  render(<ConfigField kind={kind} />);
  expect(screen.queryByRole("combobox", { name: "字体加载方式" })).not.toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Google Fonts 地址" })).toBeInTheDocument();
});
