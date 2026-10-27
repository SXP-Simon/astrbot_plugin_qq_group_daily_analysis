import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import schema from "../../../../../../_conf_schema.json";
import { renderingRuntimeSchema } from "../../../../entities/config/model/renderingConfig";
import { FieldRenderer } from "../FieldRenderer";
import { testCustomT2i } from "../../../../entities/config/api/configApi";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock("../../../../entities/config/api/configApi", () => ({ testCustomT2i: vi.fn() }));

// 从真实 schema 构造已有条目，编辑与请求用例无需重复走添加流程。
const templateDefaults: Record<string, Record<string, unknown>> = Object.fromEntries(
  Object.entries(schema.t2i_rendering.items.t2i_rendering_strategies.templates).map(([key, template]) => [key, {
    __template_key: key,
    ...Object.fromEntries(Object.entries(template.items).map(([name, field]) => [name, field.default])),
  }]),
);

function StrategiesField({ initialValue = [] }: { initialValue?: unknown }) {
  const [value, setValue] = useState<unknown>(initialValue);
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

it("从真实预设添加海外和内地方案，保留各自默认值", async () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("海外方案", { exact: true }, { timeout: 5000 }));
  expect(screen.queryByLabelText("渲染服务")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("自定义 T2I 服务地址")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "测试渲染" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("资源环境")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("内地方案", { exact: true }, { timeout: 5000 }));
  expect(JSON.parse(screen.getByTestId("strategies").textContent || "[]")).toMatchObject([
    { __template_key: "strategy", priority: 10, environment: "Overseas", google_fonts: "https://fonts.googleapis.com", timeout: 20000 },
    { __template_key: "mainland", priority: 20, environment: "Mainland", google_fonts: "https://fonts.loli.net" },
  ]);
}, 20000);

it("已有方案独立编辑资源，并按优先级更新预览", () => {
  render(<StrategiesField initialValue={[templateDefaults.strategy, templateDefaults.mainland]} />);
  fireEvent.change(screen.getAllByLabelText("模板资源 CDN", { selector: "input" })[0], { target: { value: " https://first.example/ " } });
  expect(screen.getByTestId("preview")).toHaveTextContent("https://first.example");
  fireEvent.change(screen.getAllByRole("spinbutton", { hidden: true })[0], { target: { value: "30" } });
  fireEvent.change(screen.getAllByLabelText("模板资源 CDN", { selector: "input" })[1], { target: { value: "https://second.example" } });
  expect(screen.getByTestId("preview")).toHaveTextContent("https://second.example");
  const strategies: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(strategies).toMatchObject([
    { __template_key: "strategy", priority: 30, environment: "Overseas", cdn_base_url: " https://first.example/ ", google_fonts: "https://fonts.googleapis.com", timeout: 20000 },
    { __template_key: "mainland", priority: 20, environment: "Mainland", cdn_base_url: "https://second.example", google_fonts: "https://fonts.loli.net" },
  ]);
}, 20000);

it("直接添加自定义方案，预填本地服务和超时", async () => {
  render(<StrategiesField />);
  fireEvent.click(screen.getByRole("button", { name: /添加渲染方案/ }));
  fireEvent.click(await screen.findByText("自定义 T2I 方案", { exact: true }, { timeout: 5000 }));
  expect(screen.queryByLabelText("渲染服务")).not.toBeInTheDocument();
  expect(screen.getByLabelText("自定义 T2I 服务地址")).toHaveValue("http://127.0.0.1:8999/text2img");
  expect(screen.getByRole("button", { name: "测试渲染" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("40000")).toBeInTheDocument();
  expect(JSON.parse(screen.getByTestId("strategies").textContent || "[]")).toMatchObject([{
    __template_key: "custom", environment: "Overseas", timeout: 20000, request_timeout: 40000,
  }]);
}, 20000);

it("自定义方案独立编辑等待上限、凭据、字体和资源环境", () => {
  render(<StrategiesField initialValue={[templateDefaults.custom]} />);
  fireEvent.change(screen.getByDisplayValue("40000"), { target: { value: "70000" } });
  const token = screen.getByLabelText("服务 Token（可选）");
  expect(token).toHaveAttribute("type", "password");
  fireEvent.change(token, { target: { value: "my-secret" } });
  fireEvent.change(screen.getByLabelText("Google Fonts 地址", { selector: "input" }), { target: { value: "https://my-fonts.example" } });
  fireEvent.mouseDown(screen.getByLabelText("资源环境", { selector: "input" }));
  fireEvent.click(screen.getByText("内地（Mainland）", { exact: true }));
  const data: unknown = JSON.parse(screen.getByTestId("strategies").textContent || "[]");
  expect(data).toMatchObject([{
    __template_key: "custom", environment: "Mainland", timeout: 20000, request_timeout: 70000,
    service_endpoint: "http://127.0.0.1:8999/text2img", service_token: "my-secret",
    google_fonts: "https://my-fonts.example", gstatic: "", cdn_base_url: "",
  }]);
}, 20000);

it("测试渲染读取当前未保存条目的值，并显示返回图片", async () => {
  const draft = { ...templateDefaults.custom, service_endpoint: "http://draft.example/text2img", service_token: "old-token", timeout: 12000, request_timeout: 70000 };
  vi.mocked(testCustomT2i).mockResolvedValue({ image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 100 });
  render(<StrategiesField initialValue={[draft]} />);
  fireEvent.change(screen.getByLabelText("服务 Token（可选）"), { target: { value: "my-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(testCustomT2i).toHaveBeenCalledWith({
    service_endpoint: "http://draft.example/text2img", service_token: "my-secret", timeout: 12000, request_timeout: 70000,
  });
  expect(await screen.findByAltText("T2I 测试图片")).toBeInTheDocument();
}, 20000);
