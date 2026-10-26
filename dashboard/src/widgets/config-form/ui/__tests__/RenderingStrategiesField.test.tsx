import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { renderingRuntimeSchema } from "../../../../entities/config/model/renderingConfig";
import { FieldRenderer } from "../FieldRenderer";
import { testCustomT2i } from "../../../../entities/config/api/configApi";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock("../../../../entities/config/api/configApi", () => ({ testCustomT2i: vi.fn() }));

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

it("从内地和海外预设添加方案，各轮独立编辑资源并驱动优先级预览", async () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("海外方案", { exact: true }, { timeout: 5000 }));
  expect(screen.queryByRole("combobox", { name: "渲染服务" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("自定义 T2I 服务地址")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "测试渲染" })).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "资源环境" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "模板资源 CDN" }), { target: { value: " https://first.example/ " } });
  expect(screen.getByTestId("preview")).toHaveTextContent("https://first.example");
  fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "30" } });
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("内地方案", { exact: true }, { timeout: 5000 }));
  fireEvent.change(screen.getAllByRole("combobox", { name: "模板资源 CDN" })[1], { target: { value: "https://second.example" } });
  expect(screen.getByTestId("preview")).toHaveTextContent("https://second.example");
  const strategies: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toMatchObject([
    { __template_key: "strategy", priority: 30, environment: "Overseas", cdn_base_url: " https://first.example/ ", google_fonts: "https://fonts.googleapis.com", timeout: 20000 },
    { __template_key: "mainland", priority: 20, environment: "Mainland", cdn_base_url: "https://second.example", google_fonts: "https://fonts.loli.net" },
  ]);
}, 20000);

it("直接添加自定义方案，预填本地服务并独立切换资源环境", async () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("自定义 T2I 方案", { exact: true }, { timeout: 5000 }));
  expect(screen.queryByRole("combobox", { name: "渲染服务" })).not.toBeInTheDocument();
  vi.mocked(testCustomT2i).mockResolvedValue({ image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 100 });
  expect(screen.getByLabelText("自定义 T2I 服务地址")).toHaveValue("http://127.0.0.1:8999/text2img");
  expect(screen.getByRole("button", { name: "测试渲染" })).toBeInTheDocument();
  fireEvent.change(screen.getByDisplayValue("40000"), { target: { value: "70000" } });
  const token = screen.getByLabelText("服务 Token（可选）");
  expect(token).toHaveAttribute("type", "password");
  fireEvent.change(token, { target: { value: "my-secret" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Google Fonts 地址" }), { target: { value: "https://my-fonts.example" } });
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "资源环境" }));
  fireEvent.click(screen.getByText("内地（Mainland）", { exact: true }));
  const data: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(data).toMatchObject([{
    __template_key: "custom", environment: "Mainland", timeout: 20000, request_timeout: 70000,
    service_endpoint: "http://127.0.0.1:8999/text2img", service_token: "my-secret",
    google_fonts: "https://my-fonts.example", gstatic: "", cdn_base_url: "",
  }]);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(testCustomT2i).toHaveBeenCalledWith({
    service_endpoint: "http://127.0.0.1:8999/text2img", service_token: "my-secret", timeout: 20000, request_timeout: 70000,
  });
  expect(await screen.findByAltText("T2I 测试图片")).toBeInTheDocument();
}, 20000);
