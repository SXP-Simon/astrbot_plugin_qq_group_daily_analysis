import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { testT2i } from "@/entities/config/api/configApi";
import type { T2iProbe as ProbeResult } from "@/entities/config/model/t2iProbe";
import { T2iProbe } from "@/features/test-t2i/ui/T2iProbe";
import { fetchGroupSessions } from "@/entities/group/api/groupApi";
import { useT2iProbe } from "@/features/test-t2i/model/useT2iProbe";

vi.mock("@/entities/config/api/configApi", () => ({ testT2i: vi.fn() }));
vi.mock("@/entities/group/api/groupApi", () => ({ fetchGroupSessions: vi.fn() }));

const input = {
  service_endpoint: "http://127.0.0.1:8999",
  service_token: "draft-secret",
  timeout: 20000,
  request_timeout: 40000,
};
const result: ProbeResult = { image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 1200 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchGroupSessions).mockResolvedValue([
    { group_id: "123", group_name: "日常交流群", platform: "onebot_1" },
  ]);
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
  vi.mocked(testT2i)
    .mockResolvedValueOnce(result)
    .mockRejectedValueOnce(new Error("HTTP 401，请检查服务 Token"));
  render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  expect(await screen.findByText("HTTP 401，请检查服务 Token")).toBeInTheDocument();
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
});

it.each([
  { service_endpoint: "http://another.local" },
  { service_token: "new-secret" },
  { timeout: 10000 },
  { request_timeout: 60000 },
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
  fireEvent.click(screen.getByRole("button", { name: /^测试使用的 AstrBot 配置：/ }));
  fireEvent.click(await screen.findByText("日常交流群（123 · onebot_1）"));
  expect(screen.queryByAltText("T2I 测试图片")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  expect(testT2i).toHaveBeenLastCalledWith({ ...host, group_id: "123", platform_id: "onebot_1" });
});

it("简洁说明宿主和自定义测试的使用范围", () => {
  const view = render(<T2iProbe input={{ render_service: "astrbot" }} />);
  expect(screen.getByText(/未绑定配置的群使用默认配置/)).toBeInTheDocument();
  expect(screen.getByText(/测试检查 T2I 服务是否可用，不检查模板图片和字体/)).toBeInTheDocument();
  view.rerender(<T2iProbe input={{ render_service: "custom" }} />);
  expect(
    screen.getByText(/无需保存即可测试当前 T2I（文字转图片）服务地址和 Token/),
  ).toBeInTheDocument();
  expect(screen.getByText(/不会调用大模型或发到群里/)).toBeInTheDocument();
});

it("群列表读取失败时保留默认配置测试", async () => {
  vi.mocked(fetchGroupSessions).mockRejectedValue(new Error("离线"));
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
  vi.mocked(testT2i)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        finishOld = resolve;
      }),
    )
    .mockResolvedValueOnce(result);
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
  vi.mocked(testT2i).mockReturnValue(
    new Promise((_resolve, reject) => {
      fail = reject;
    }),
  );
  const view = render(<T2iProbe input={input} />);
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  view.unmount();
  await act(async () => fail?.(new Error("旧请求失败")));
});

it("相同群号的不同平台可分别选择并传入正确会话", async () => {
  vi.mocked(fetchGroupSessions).mockResolvedValue([
    { group_id: "123", group_name: "群一", platform: "onebot_1" },
    { group_id: "123", group_name: "群二", platform: "onebot_2" },
  ]);
  vi.mocked(testT2i).mockResolvedValue(result);
  render(<T2iProbe input={{ render_service: "astrbot" }} />);
  fireEvent.click(screen.getByRole("button", { name: /^测试使用的 AstrBot 配置：/ }));
  expect(await screen.findByText("群一（123 · onebot_1）")).toBeInTheDocument();
  fireEvent.click(screen.getByText("群二（123 · onebot_2）"));
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByAltText("T2I 测试图片");
  expect(testT2i).toHaveBeenCalledWith({
    render_service: "astrbot",
    group_id: "123",
    platform_id: "onebot_2",
  });
});

it("筛选群聊后选择回到入口焦点，仍按平台和群号测试", async () => {
  vi.mocked(testT2i).mockResolvedValue(result);
  render(<T2iProbe input={{ render_service: "astrbot" }} />);
  const opener = screen.getByRole("button", { name: /^测试使用的 AstrBot 配置：/ });
  opener.focus();
  fireEvent.click(opener);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "onebot_1" } });
  fireEvent.click(await screen.findByRole("button", { name: "日常交流群（123 · onebot_1）" }));
  await waitFor(() => expect(opener).toHaveFocus());
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByRole("img", { name: "T2I 测试图片" });
  expect(testT2i).toHaveBeenLastCalledWith({
    render_service: "astrbot",
    group_id: "123",
    platform_id: "onebot_1",
  });
});

it("Typst 测试保留本地字体和编译器说明，不加载宿主群聊选项", async () => {
  vi.mocked(testT2i).mockResolvedValue(result);
  render(<T2iProbe input={{ render_service: "typst" }} />);
  expect(screen.getByText(/测试插件数据目录中的字体和 Typst 独立编译器/)).toBeVisible();
  expect(screen.getByText(/不会下载角色素材、调用大模型或发到群里/)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /^测试使用的 AstrBot 配置：/ }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "测试渲染" }));
  await screen.findByRole("img");
  expect(fetchGroupSessions).not.toHaveBeenCalled();
  expect(testT2i).toHaveBeenCalledWith({ render_service: "typst" });
});

it("同一批次重复发起测试也只发送一次请求", async () => {
  let finish!: (value: ProbeResult) => void;
  vi.mocked(testT2i).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result: hook } = renderHook(() => useT2iProbe(input));
  let first!: Promise<void>;
  act(() => {
    first = hook.current.run();
    void hook.current.run();
  });
  expect(testT2i).toHaveBeenCalledTimes(1);
  await act(async () => {
    finish(result);
    await first;
  });
  expect(hook.current.loading).toBe(false);
  expect(hook.current.result).toEqual(result);
});
