import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { renderingRuntimeSchema } from "../../../../entities/config/model/renderingConfig";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

function StrategiesField() {
  const [value, setValue] = useState<unknown>([]);
  const preview = renderingRuntimeSchema.safeParse({
    t2i_mainland_cdn_base_url: "https://mainland.example",
    t2i_overseas_cdn_base_url: "https://overseas.example",
    t2i_rendering_strategies: value,
  });
  return <>
    <FieldRenderer
      fieldKey="t2i_rendering_strategies"
      fieldSchema={schema.t2i_rendering.items.t2i_rendering_strategies}
      value={value}
      onChange={setValue}
    />
    <pre data-testid="strategies">{JSON.stringify(value)}</pre>
    <output data-testid="preview">{preview.success ? preview.data.t2i_cdn_base_url : ""}</output>
  </>;
}

it("可添加多轮、设置环境和优先级，并驱动第一优先级预览", () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加 渲染方案/ }));
  let strategies: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toHaveLength(1);
  expect(strategies).toMatchObject([{ __template_key: "strategy", priority: 10, environment: "Overseas", timeout: 20000 }]);
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "资源环境" }));
  fireEvent.click(screen.getByText("内地（Mainland）"));
  expect(screen.getByTestId("preview")).toHaveTextContent("https://mainland.example");
  fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: /添加 渲染方案/ }));
  strategies = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toHaveLength(2);
  expect(strategies).toMatchObject([{ priority: 20, environment: "Mainland" }, { priority: 10, environment: "Overseas" }]);
  expect(screen.getByTestId("preview")).toHaveTextContent("https://overseas.example");
});

it("切换到自定义服务后才显示地址与隐藏输入的 Token，切回后保留草稿", () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加 渲染方案/ }));
  expect(screen.queryByText("自定义 T2I 服务地址")).not.toBeInTheDocument();
  const service = screen.getByRole("combobox", { name: "渲染服务" });
  fireEvent.mouseDown(service);
  fireEvent.click(screen.getByText("自定义 T2I 服务", { exact: true }));
  const token = screen.getByLabelText("服务 Token（可选）");
  expect(token).toHaveAttribute("type", "password");
  fireEvent.change(token, { target: { value: "my-secret" } });
  expect(screen.getByText("自定义 T2I 服务地址")).toBeVisible();
  fireEvent.mouseDown(service);
  fireEvent.click(screen.getByText("跟随 AstrBot", { exact: true }));
  expect(screen.queryByLabelText("服务 Token（可选）")).not.toBeInTheDocument();
  const data: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(data).toMatchObject([{ render_service: "astrbot", service_token: "my-secret" }]);
});
