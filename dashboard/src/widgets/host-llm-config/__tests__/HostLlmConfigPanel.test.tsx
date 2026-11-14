import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { HostLlmConfigPanel } from "@/widgets/host-llm-config/ui/HostLlmConfigPanel";
import { fetchHostLlmConfig } from "@/entities/config/api/hostLlmApi";
import { fetchGroupSessions } from "@/entities/group/api/groupApi";
import { describeLlmChains, type HostLlmConfig } from "@/entities/config/model/hostLlmConfig";

vi.mock("@/entities/config/api/hostLlmApi", () => ({ fetchHostLlmConfig: vi.fn() }));
vi.mock("@/entities/group/api/groupApi", () => ({ fetchGroupSessions: vi.fn() }));

const host: HostLlmConfig = {
  primary_id: "a",
  fallback_ids: ["b", "a", "b", "removed"],
  providers: [
    { id: "a", name: "宿主主模型", model: "model-a", available: true },
    { id: "b", name: "宿主备用模型", model: "model-b", available: true },
    { id: "p", name: "插件专用模型", model: "model-p", available: true },
    { id: "removed", name: "已删除模型", model: "", available: false },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchHostLlmConfig).mockResolvedValue({ ...host, fallback_ids: ["b", "removed"] });
  vi.mocked(fetchGroupSessions).mockResolvedValue([
    { platform: "bot-a", group_id: "123", group_name: "示例群" },
  ]);
});

it("展示留空继承、专用模型优先及显式主模型抑制宿主回退", () => {
  const inherited = describeLlmChains(host, { topic_provider_id: "p" });
  expect(inherited.inherit).toBe(true);
  expect(inherited.rows[0].models.map((item) => item.id)).toEqual(["a", "b"]);
  expect(inherited.rows[1].models.map((item) => item.id)).toEqual(["p", "a", "b"]);
  const explicit = describeLlmChains(host, { llm_provider_id: "p", topic_provider_id: "b" });
  expect(explicit.inherit).toBe(false);
  expect(explicit.rows[0].models.map((item) => item.id)).toEqual(["p"]);
  expect(explicit.rows[1].models.map((item) => item.id)).toEqual(["b", "p"]);
  const missing = describeLlmChains(host, { llm_provider_id: "removed" });
  expect(missing.rows[0].missing).toEqual(["removed"]);
  expect(missing.rows[0].models.map((item) => item.id)).toEqual(["a"]);
});

it("只读展示宿主模型，草稿预览和刷新不修改插件表单", async () => {
  const draft = { llm_provider_id: "p" };
  const view = render(<HostLlmConfigPanel draft={draft} dirty />);
  await screen.findByText("已删除模型");
  expect(screen.getByText("宿主只读")).toBeVisible();
  expect(screen.getByText(/未保存的预览/)).toBeVisible();
  expect(screen.getByText(/已指定插件主 LLM/)).toBeVisible();
  expect(screen.queryByRole("button", { name: /保存/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "刷新宿主信息" }));
  await waitFor(() => expect(fetchHostLlmConfig).toHaveBeenCalledTimes(2));
  await screen.findByText("已删除模型");
  // 检查刷新完成后的实际展示，不能仅证明传入的草稿对象没有被修改。
  expect(screen.getByText(/未保存的预览/)).toBeVisible();
  expect(screen.getByText(/已指定插件主 LLM/)).toBeVisible();
  const chains = screen.getAllByRole("definition");
  expect(chains).toHaveLength(6);
  for (const chain of chains) {
    expect(within(chain).getByText("插件专用模型")).toBeVisible();
    expect(within(chain).queryByText("宿主主模型")).not.toBeInTheDocument();
    expect(within(chain).queryByText("宿主备用模型")).not.toBeInTheDocument();
  }
  expect(draft).toEqual({ llm_provider_id: "p" });
  view.rerender(<HostLlmConfigPanel draft={{ llm_provider_id: "" }} dirty />);
  expect(await screen.findByText(/主 LLM 留空/)).toBeVisible();
  expect(fetchHostLlmConfig).toHaveBeenCalledTimes(2);
});

it("切换群会话时不显示旧范围结果，迟到响应不覆盖新会话", async () => {
  let resolveDefault!: (data: HostLlmConfig) => void;
  vi.mocked(fetchHostLlmConfig).mockReturnValueOnce(
    new Promise((resolve) => {
      resolveDefault = resolve;
    }),
  );
  vi.mocked(fetchHostLlmConfig).mockResolvedValueOnce({
    primary_id: "b",
    fallback_ids: [],
    providers: [host.providers[1]],
  });
  render(<HostLlmConfigPanel draft={{}} dirty={false} />);
  fireEvent.click(screen.getByRole("button", { name: /查看范围：/ }));
  const dialog = screen.getByRole("dialog", { name: "查看范围" });
  fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "123" } });
  fireEvent.click(await within(dialog).findByRole("button", { name: /示例群/ }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await waitFor(() =>
    expect(fetchHostLlmConfig).toHaveBeenLastCalledWith({
      platform: "bot-a",
      group_id: "123",
      group_name: "示例群",
    }),
  );
  await screen.findByText("未配置回退模型");
  await act(async () => {
    resolveDefault(host);
  });
  expect(screen.queryByText("宿主主模型")).not.toBeInTheDocument();
  expect(screen.getByText("未配置回退模型")).toBeVisible();
});

it("读取失败明确显示错误，刷新成功后恢复展示", async () => {
  vi.mocked(fetchHostLlmConfig).mockRejectedValueOnce(new Error("暂不可用"));
  render(<HostLlmConfigPanel draft={{}} dirty={false} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("读取失败");
  expect(screen.queryByText("未配置回退模型")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "刷新宿主信息" }));
  await screen.findByText("已删除模型");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("宿主回执超时后恢复刷新，重试成功仍保留草稿调用顺序", async () => {
  const actualApi = await vi.importActual<typeof import("@/entities/config/api/hostLlmApi")>(
    "@/entities/config/api/hostLlmApi",
  );
  vi.mocked(fetchHostLlmConfig).mockImplementation(actualApi.fetchHostLlmConfig);
  const previousBridge = window.AstrBotPluginPage;
  const bridgeGet = vi.fn().mockReturnValue(new Promise<never>(() => {}));
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    apiGet: bridgeGet,
    apiPost: vi.fn(),
    subscribeSSE: async () => "unused",
    unsubscribeSSE: () => {},
  };
  vi.useFakeTimers();
  try {
    render(<HostLlmConfigPanel draft={{ llm_provider_id: "p" }} dirty />);
    expect(screen.getByRole("button", { name: "刷新宿主信息" })).toBeDisabled();
    // 使用真实接口封装与通信层，确认丢失回执确实会触发超时，而非模拟一次拒绝。
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(screen.getByRole("alert")).toHaveTextContent("读取失败");
    expect(screen.getByRole("button", { name: "刷新宿主信息" })).toBeEnabled();
    bridgeGet.mockResolvedValue({ status: "ok", data: { ...host, fallback_ids: ["b"] } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "刷新宿主信息" }));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/未保存的预览/)).toBeVisible();
    expect(screen.getAllByRole("definition").map((row) => row.textContent)).toEqual(
      Array(6).fill("插件专用模型"),
    );
    expect(bridgeGet).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    window.AstrBotPluginPage = previousBridge;
    vi.useRealTimers();
  }
});
