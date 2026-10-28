import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { testT2i } from "../../../../entities/config/api/configApi";
import type { T2iProbe as ProbeResult } from "../../../../entities/config/model/t2iProbe";
import { T2iProbe } from "../T2iProbe";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";

vi.mock("../../../../entities/config/api/configApi", () => ({ testT2i: vi.fn() }));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));

const input = { service_endpoint: "http://127.0.0.1:8999", service_token: "draft-secret", timeout: 20000, request_timeout: 40000 };
const result: ProbeResult = { image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 1200 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchDistinctGroups).mockResolvedValue([{ group_id: "123", group_name: "日常交流群", platform: "onebot_1" }]);
});

it("使用未保存的当前配置，仅在页面显示图片和耗时，不回显 Token", async () => {
  vi.mocked(testT2i).mockResolvedValue(result);
  render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(testT2i).toHaveBeenCalledWith(input);
  expect(await screen.findByText("测试图片已生成，用时 1.20 秒")).toBeInTheDocument();
  expect(screen.getByAltText("T2I 测试图片")).toHaveAttribute("src", result.image_data_url);
  expect(screen.queryByText("draft-secret")).not.toBeInTheDocument();
});

it("失败显示原因，不留下成功结果", async () => {
  vi.mocked(testT2i).mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("HTTP 401，请检查服务 Token"));
  render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(await screen.findByText("HTTP 401，请检查服务 Token")).toBeInTheDocument();
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
});

it.each([
  { service_endpoint: "http://another.local" }, { service_token: "new-secret" },
  { timeout: 10000 }, { request_timeout: 60000 },
  { render_service: "astrbot" },
])("修改配置后清除已有结果：%j", async (change) => {
  vi.mocked(testT2i).mockResolvedValue(result);
  const view = render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  await act(async () => view.rerender(<T2iProbe input={{ ...input, ...change }} />));
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
});

it("宿主方案可测试默认配置和群聊配置，切换目标后清除旧结果", async () => {
  vi.mocked(testT2i).mockResolvedValue(result);
  const host = { render_service: "astrbot", timeout: 12000 };
  render(<T2iProbe input={host} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  expect(testT2i).toHaveBeenLastCalledWith(host);
  fireEvent.mouseDown(screen.getByLabelText("测试使用的 AstrBot 配置", { selector: "input" }));
  fireEvent.click(await screen.findByText("日常交流群（123 · onebot_1）"));
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  expect(testT2i).toHaveBeenLastCalledWith({ ...host, group_id: "123", platform_id: "onebot_1" });
});

it("简洁说明宿主和自定义测试的使用范围", () => {
  const view = render(<T2iProbe input={{ render_service: "astrbot" }} />);
  expect(screen.getByText(/未绑定配置的群使用默认配置/)).toBeInTheDocument();
  expect(screen.getByText(/测试不调用大模型，也不会发到群里/)).toBeInTheDocument();
  view.rerender(<T2iProbe input={{ render_service: "custom" }} />);
  expect(screen.getByText(/无需保存即可测试当前服务地址和 Token/)).toBeInTheDocument();
  expect(screen.getByText(/模板素材请通过报告确认/)).toBeInTheDocument();
});

it("群列表读取失败时保留默认配置测试", async () => {
  vi.mocked(fetchDistinctGroups).mockRejectedValue(new Error("离线"));
  vi.mocked(testT2i).mockResolvedValue(result);
  const host = { render_service: "astrbot" };
  render(<T2iProbe input={host} />);
  await screen.findByText("群列表暂时无法读取，可以先测试 AstrBot 默认配置。");
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  expect(testT2i).toHaveBeenCalledWith(host);
});

it("旧请求晚到不能覆盖新请求；等待期间不重复提交", async () => {
  let finishOld: ((value: ProbeResult) => void) | undefined;
  vi.mocked(testT2i).mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve; })).mockResolvedValueOnce(result);
  const view = render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  fireEvent.click(screen.getByRole("button", { name: /正在生成测试图…/ }));
  expect(testT2i).toHaveBeenCalledTimes(1);
  view.rerender(<T2iProbe input={{ ...input, service_token: "changed" }} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByText("测试图片已生成，用时 1.20 秒");
  await act(async () => finishOld?.({ ...result, elapsed_ms: 9999 }));
  expect(screen.queryByText(/9.99 秒/)).not.toBeInTheDocument();
});

it("卸载后不处理晚到的失败", async () => {
  let fail: ((error: Error) => void) | undefined;
  vi.mocked(testT2i).mockReturnValue(new Promise((_resolve, reject) => { fail = reject; }));
  const view = render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  view.unmount();
  await act(async () => fail?.(new Error("旧请求失败")));
});
