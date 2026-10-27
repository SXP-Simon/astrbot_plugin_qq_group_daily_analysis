import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RenderAttemptsTable } from "../RenderAttemptsTable";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("每轮显示实际服务地址，区分资源环境与T2I服务", () => {
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


it("主动取消的轮次显示已停止", () => {
  render(<RenderAttemptsTable attempts={[{ attempt: 1, status: "cancelled", error: "本轮图片渲染已停止。" }]} />);
  expect(screen.getByText("已停止")).toBeVisible();
  expect(screen.queryByText("渲染失败")).not.toBeInTheDocument();
});

it("展示方案、两种超时、耗时及独立资源地址", () => {
  render(<RenderAttemptsTable attempts={[{
    attempt: 2, status: "success", strategy_name: "我的备用服务", priority: 30,
    service_type: "custom", font_mode: "network", resource_environment: "Mainland",
    duration_ms: 3240, render_timeout_ms: 20000, request_timeout_ms: 40000,
    render_service: { config_lookup: "本轮自定义 T2I 服务", configured_endpoint: "http://renderer:8999" },
    resource_urls: { cdn_base_url: "https://cdn.example", google_fonts: "https://fonts.example/css", gstatic: "https://static.example" },
  }]} />);
  expect(screen.getByText(/我的备用服务 · 优先级 30 · 自定义 T2I/)).toHaveTextContent("耗时：3.24s · 渲染超时：20.00s · 请求等待上限：40.00s");
  expect(screen.getByText("模板资源：https://cdn.example")).toBeVisible();
  expect(screen.getByText("字体 CSS：https://fonts.example/css")).toBeVisible();
  expect(screen.getByText("字体文件：https://static.example")).toBeVisible();
  expect(screen.getByText("配置来源：本轮自定义 T2I 服务")).toBeVisible();
});

it("运行中的轮次不显示失败，本地字体不展示未使用的在线字体地址", () => {
  render(<RenderAttemptsTable attempts={[{
    status: "running", service_type: "custom", font_mode: "local",
    resource_urls: { cdn_base_url: "https://cdn.example", google_fonts: "https://unused.example", gstatic: "https://unused-static.example" },
  }]} />);
  expect(screen.getByText("正在渲染")).toBeVisible();
  expect(screen.getByText(/字体：本地已安装字体/)).toBeVisible();
  expect(screen.getByText("模板资源：https://cdn.example")).toBeVisible();
  expect(screen.queryByText("渲染失败")).not.toBeInTheDocument();
  expect(screen.queryByText(/字体 CSS|字体文件/)).not.toBeInTheDocument();
});

it("忽略格式异常的字段，不影响旧记录的其他信息", () => {
  render(<RenderAttemptsTable attempts={[{ status: "failed", duration_ms: "slow", resource_urls: [], render_service: "old", error: "HTTP 503" }]} />);
  expect(screen.getByText("渲染失败")).toBeVisible();
  expect(screen.getByText("HTTP 503")).toBeVisible();
  expect(screen.queryByText(/耗时：|服务：/)).not.toBeInTheDocument();
});
