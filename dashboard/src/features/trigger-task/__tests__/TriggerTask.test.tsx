import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { TriggerTaskModal } from "@/features/trigger-task/ui/TriggerTaskModal";
import { useTriggerTask } from "@/features/trigger-task/model/useTriggerTask";
import {
  fetchConnectedPlatforms,
  triggerNewTask,
  type ConnectedPlatform,
  type TriggerTaskResult,
} from "@/entities/task/api/taskApi";
import { fetchProviderList } from "@/entities/trace/api/traceApi";
import { fetchReportTemplates } from "@/entities/report/api/reportApi";
import type { GroupItem } from "@/entities/group/model/types";

vi.mock("@/entities/task/api/taskApi", () => ({
  fetchConnectedPlatforms: vi.fn(),
  triggerNewTask: vi.fn(),
}));
vi.mock("@/entities/trace/api/traceApi", () => ({ fetchProviderList: vi.fn() }));
vi.mock("@/entities/report/api/reportApi", () => ({ fetchReportTemplates: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn() } }));
const platforms: ConnectedPlatform[] = [
  { id: "qq-main", type: "aiocqhttp", display_name: "QQ 主号", label: "QQ 主号" },
  { id: "tg-main", type: "telegram", display_name: "TG 主号", label: "TG 主号" },
];
const groups: GroupItem[] = [
  { group_id: "same", group_name: "QQ 示例", platform: "aiocqhttp" },
  { group_id: "same", group_name: "TG 示例", platform: "telegram" },
  { group_id: "unique", group_name: "唯一群聊", platform: "aiocqhttp" },
];
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function Fixture({ onSuccess = vi.fn() }: { onSuccess?: () => void }) {
  const vm = useTriggerTask(groups, onSuccess);
  return (
    <>
      <button onClick={vm.handleOpen}>发起分析</button>
      <TriggerTaskModal
        open={vm.open}
        groupId={vm.groupId}
        groupName={vm.groupName}
        platform={vm.platform}
        providerId={vm.providerId}
        templateName={vm.templateName}
        submitting={vm.submitting}
        connectedPlatforms={vm.connectedPlatforms}
        loadingPlatforms={vm.loadingPlatforms}
        providers={vm.providers}
        loadingProviders={vm.loadingProviders}
        templates={vm.templates}
        loadingTemplates={vm.loadingTemplates}
        templatesError={vm.templatesError}
        optionsError={vm.optionsError}
        onRefreshTemplates={() => void vm.refreshTemplates()}
        onRefreshOptions={vm.refreshOptions}
        onGroupIdChange={vm.setGroupId}
        onGroupNameChange={vm.setGroupName}
        onPlatformChange={vm.setPlatform}
        onProviderChange={vm.setProviderId}
        onTemplateChange={vm.setTemplateName}
        onClose={vm.handleClose}
        onSubmit={vm.handleSubmit}
      />
    </>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchConnectedPlatforms).mockResolvedValue(platforms);
  vi.mocked(fetchProviderList).mockResolvedValue([{ id: "deepseek", name: "示例模型" }]);
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "ATRI", label: "亚托莉", has_image: true },
  ]);
  vi.mocked(triggerNewTask).mockResolvedValue({ status: "ok", trace_id: "new-task" });
});

it("保留所有输入与指定选项，等待提交时不能重复发送或关闭，成功后恢复入口焦点", async () => {
  const submitted = deferred<TriggerTaskResult>();
  vi.mocked(triggerNewTask).mockReturnValueOnce(submitted.promise);
  const onSuccess = vi.fn();
  render(<Fixture onSuccess={onSuccess} />);
  const trigger = screen.getByRole("button", { name: "发起分析" });
  act(() => trigger.focus());
  fireEvent.click(trigger);
  const id = screen.getByRole("textbox", { name: "群号 / 会话标识" });
  expect(id).toHaveFocus();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "报告模板" })).toBeEnabled());
  fireEvent.change(id, { target: { value: "  target-id  " } });
  fireEvent.change(screen.getByRole("textbox", { name: "群名称（选填）" }), {
    target: { value: " 示例群 " },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "平台" }), {
    target: { value: "tg-main" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "模型" }), {
    target: { value: "deepseek" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "报告模板" }), {
    target: { value: "ATRI" },
  });
  const form = id.closest("form")!;
  fireEvent.submit(form);
  fireEvent.submit(form);
  expect(triggerNewTask).toHaveBeenCalledOnce();
  expect(triggerNewTask).toHaveBeenCalledWith("target-id", "示例群", "tg-main", "deepseek", "ATRI");
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.getByRole("dialog")).toBeVisible();
  expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  await act(async () => submitted.resolve({ status: "ok", trace_id: "new-task" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(toast.success).toHaveBeenCalledWith("分析任务已提交", {
    description: "任务编号：new-task",
  });
  expect(onSuccess).toHaveBeenCalledOnce();
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("失败在表单内反馈且保留输入，重试默认选择不传额外覆盖参数", async () => {
  vi.mocked(triggerNewTask).mockRejectedValueOnce(new Error("该群已有任务正在运行"));
  render(<Fixture />);
  fireEvent.click(screen.getByRole("button", { name: "发起分析" }));
  const id = screen.getByRole("textbox", { name: "群号 / 会话标识" });
  fireEvent.change(id, { target: { value: "retry-group" } });
  fireEvent.submit(id.closest("form")!);
  expect(await screen.findByRole("alert")).toHaveTextContent("该群已有任务正在运行");
  expect(id).toHaveValue("retry-group");
  expect(toast.success).not.toHaveBeenCalled();
  fireEvent.submit(id.closest("form")!);
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(triggerNewTask).toHaveBeenLastCalledWith("retry-group", "", "auto", undefined, undefined);
});

it("平台或模型读取失败可重试，模板能力失败不隐藏默认选择", async () => {
  vi.mocked(fetchConnectedPlatforms).mockRejectedValueOnce(new Error("离线"));
  vi.mocked(fetchReportTemplates).mockRejectedValueOnce(new Error("离线"));
  render(<Fixture />);
  fireEvent.click(screen.getByRole("button", { name: "发起分析" }));
  expect(await screen.findByText("平台列表未能读取，可重试加载或使用默认选择。")).toBeVisible();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "报告模板" })).toBeEnabled());
  expect(
    within(screen.getByRole("combobox", { name: "平台" })).getByRole("option", {
      name: "自动识别平台",
    }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重新加载选项" }));
  fireEvent.click(screen.getByRole("button", { name: "重新加载模板" }));
  await waitFor(() => expect(screen.queryAllByRole("alert")).toHaveLength(0));
  expect(screen.getByRole("option", { name: "QQ 主号" })).toBeInTheDocument();
});

describe("发起分析状态边界", () => {
  it("同号多平台不猜测，唯一群聊补全实例；手选字段不被覆盖", async () => {
    const { result } = renderHook(() => useTriggerTask(groups));
    act(() => result.current.handleOpen());
    await waitFor(() => expect(result.current.loadingPlatforms).toBe(false));
    act(() => result.current.setGroupId("same"));
    expect(result.current.platform).toBe("auto");
    expect(result.current.groupName).toBe("");
    act(() => result.current.setGroupId("unique"));
    expect(result.current.platform).toBe("qq-main");
    expect(result.current.groupName).toBe("唯一群聊");
    act(() => result.current.setGroupId("same"));
    expect(result.current.platform).toBe("auto");
    expect(result.current.groupName).toBe("");
    act(() => {
      result.current.setPlatform("tg-main");
      result.current.setGroupName("手动名称");
    });
    act(() => result.current.setGroupId("same"));
    expect(result.current.platform).toBe("tg-main");
    expect(result.current.groupName).toBe("手动名称");
  });

  it("关闭后重新打开，较早的选项请求不能覆盖新列表", async () => {
    const old = deferred<ConnectedPlatform[]>();
    vi.mocked(fetchConnectedPlatforms).mockReturnValueOnce(old.promise);
    const { result } = renderHook(() => useTriggerTask());
    act(() => result.current.handleOpen());
    act(() => result.current.handleClose());
    act(() => result.current.handleOpen());
    await waitFor(() => expect(result.current.loadingPlatforms).toBe(false));
    await act(async () => old.resolve([]));
    expect(result.current.connectedPlatforms).toEqual(platforms);
  });

  it("缺失群号、失效模板不会发送，重复调用提交函数只产生一次请求", async () => {
    const { result } = renderHook(() => useTriggerTask());
    act(() => result.current.handleOpen());
    await waitFor(() => expect(result.current.loadingTemplates).toBe(false));
    await act(async () => {
      await expect(result.current.handleSubmit()).rejects.toThrow("请输入群聊");
    });
    act(() => {
      result.current.setGroupId("id");
      result.current.setTemplateName("removed");
    });
    await act(async () => {
      await expect(result.current.handleSubmit()).rejects.toThrow("当前不可用");
    });
    expect(triggerNewTask).not.toHaveBeenCalled();
    act(() => result.current.setTemplateName("auto"));
    const response = deferred<TriggerTaskResult>();
    vi.mocked(triggerNewTask).mockReturnValueOnce(response.promise);
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.handleSubmit();
    });
    await act(() => result.current.handleSubmit());
    expect(triggerNewTask).toHaveBeenCalledOnce();
    act(() => result.current.handleClose());
    expect(result.current.open).toBe(true);
    await act(async () => {
      response.resolve({ status: "ok", trace_id: "new-task" });
      await pending;
    });
  });

  it("卸载后不弹成功提示，列表刷新异常也不能冒充提交失败", async () => {
    const response = deferred<TriggerTaskResult>();
    vi.mocked(triggerNewTask).mockReturnValueOnce(response.promise);
    const success = vi.fn();
    const first = renderHook(() => useTriggerTask([], success));
    act(() => first.result.current.handleOpen());
    act(() => first.result.current.setGroupId("id"));
    let pending!: Promise<void>;
    act(() => {
      pending = first.result.current.handleSubmit();
    });
    first.unmount();
    await act(async () => {
      response.resolve({ status: "ok", trace_id: "new-task" });
      await pending;
    });
    expect(toast.success).not.toHaveBeenCalled();
    expect(success).not.toHaveBeenCalled();
    const next = renderHook(() =>
      useTriggerTask([], () => {
        throw new Error("刷新失败");
      }),
    );
    act(() => next.result.current.handleOpen());
    act(() => next.result.current.setGroupId("id"));
    await act(() => next.result.current.handleSubmit());
    expect(toast.success).toHaveBeenCalledOnce();
    expect(toast.warning).toHaveBeenCalledWith("任务已提交，列表未能更新。请手动刷新查看。");
    expect(next.result.current.open).toBe(false);
  });
});
