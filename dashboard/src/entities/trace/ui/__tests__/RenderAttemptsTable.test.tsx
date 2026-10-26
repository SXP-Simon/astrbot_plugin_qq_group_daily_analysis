import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RenderAttemptsTable } from "../RenderAttemptsTable";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("每轮显示实际服务地址，区分资源环境与截图服务", () => {
  render(<RenderAttemptsTable attempts={[
    { attempt: 1, status: "failed", resource_environment: "Overseas", render_service: { config_lookup: "本轮自定义 T2I 服务", configured_endpoint: "http://127.0.0.1:8999/text2img" }, error: "HTTP 503" },
    { attempt: 2, status: "success", resource_environment: "Mainland", render_service: { configured_endpoint: "使用宿主默认地址池" } },
  ]} />);
  expect(screen.getByText("服务：http://127.0.0.1:8999/text2img")).toBeVisible();
  expect(screen.getByText("服务：使用宿主默认地址池")).toBeVisible();
  expect(screen.getByText("渲染成功")).toBeVisible();
});

it("没有服务信息的旧记录仍可显示", () => {
  render(<RenderAttemptsTable attempts={[{ attempt: 1, status: "success" }]} />);
  expect(screen.getByText("渲染成功")).toBeVisible();
  expect(screen.queryByText(/服务：/)).not.toBeInTheDocument();
});
