import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { testCustomT2i } from "../../../../entities/config/api/configApi";
import type { CustomT2iProbe as ProbeResult } from "../../../../entities/config/model/customT2iProbe";
import { CustomT2iProbe } from "../CustomT2iProbe";

vi.mock("../../../../entities/config/api/configApi", () => ({ testCustomT2i: vi.fn() }));

const input = { service_endpoint: "http://127.0.0.1:8999", service_token: "draft-secret", timeout: 20000, request_timeout: 40000 };
const result: ProbeResult = { image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 1200 };
beforeEach(() => vi.resetAllMocks());

it("使用未保存的当前配置，仅在页面显示图片和耗时，不回显 Token", async () => {
  vi.mocked(testCustomT2i).mockResolvedValue(result);
  render(<CustomT2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(testCustomT2i).toHaveBeenCalledWith(input);
  expect(await screen.findByText("测试图片已生成，用时 1.20 秒")).toBeInTheDocument();
  expect(screen.getByAltText("T2I 测试图片")).toHaveAttribute("src", result.image_data_url);
  expect(screen.queryByText("draft-secret")).not.toBeInTheDocument();
});

it("失败显示原因，不留下成功结果", async () => {
  vi.mocked(testCustomT2i).mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("HTTP 401，请检查服务 Token"));
  render(<CustomT2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(await screen.findByText("HTTP 401，请检查服务 Token")).toBeInTheDocument();
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
});

it.each([
  { service_endpoint: "http://another.local" }, { service_token: "new-secret" },
  { timeout: 10000 }, { request_timeout: 60000 },
])("修改配置后清除已有结果：%j", async (change) => {
  vi.mocked(testCustomT2i).mockResolvedValue(result);
  const view = render(<CustomT2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  view.rerender(<CustomT2iProbe input={{ ...input, ...change }} />);
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
});

it("旧请求晚到不能覆盖新请求；等待期间不重复提交", async () => {
  let finishOld: ((value: ProbeResult) => void) | undefined;
  vi.mocked(testCustomT2i).mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve; })).mockResolvedValueOnce(result);
  const view = render(<CustomT2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  fireEvent.click(screen.getByRole("button", { name: /正在生成测试图…/ }));
  expect(testCustomT2i).toHaveBeenCalledTimes(1);
  view.rerender(<CustomT2iProbe input={{ ...input, service_token: "changed" }} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByText("测试图片已生成，用时 1.20 秒");
  await act(async () => finishOld?.({ ...result, elapsed_ms: 9999 }));
  expect(screen.queryByText(/9.99 秒/)).not.toBeInTheDocument();
});

it("卸载后不处理晚到的失败", async () => {
  let fail: ((error: Error) => void) | undefined;
  vi.mocked(testCustomT2i).mockReturnValue(new Promise((_resolve, reject) => { fail = reject; }));
  const view = render(<CustomT2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  view.unmount();
  await act(async () => fail?.(new Error("旧请求失败")));
});
