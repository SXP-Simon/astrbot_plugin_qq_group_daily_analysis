import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { message } from "antd";
import { fetchActiveTasks, cancelActiveTask } from "../../../../entities/task/api/taskApi";
import { fetchMetricsSummary } from "../../../../entities/metric/api/metricApi";
import type { ActiveTask } from "../../../../entities/task/model/types";
import { useOverviewViewModel } from "../useOverviewViewModel";
import { mockMetricsSummary } from "../../../../mocks/data/metrics";

vi.mock("antd", () => ({ message: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../../../entities/task/api/taskApi", () => ({
  fetchActiveTasks: vi.fn(),
  cancelActiveTask: vi.fn(),
}));
vi.mock("../../../../entities/metric/api/metricApi", () => ({ fetchMetricsSummary: vi.fn() }));

const task: ActiveTask = {
  task_id: "WEB",
  group_id: "GROUP",
  group_name: "测试群",
  platform: "official",
  trigger_type: "web_ui",
  current_stage: "LLM_ANALYSIS",
  started_at: Date.now() / 1000,
  duration_s: 0,
  last_heartbeat: Date.now() / 1000,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchActiveTasks).mockResolvedValue([task]);
  vi.mocked(fetchMetricsSummary).mockResolvedValue(mockMetricsSummary);
});
afterEach(() => vi.restoreAllMocks());

it.each([true, false])("中止回执 %s 提供明确反馈且失败时保留任务", async (accepted) => {
  vi.mocked(cancelActiveTask).mockResolvedValue(accepted);
  const { result } = renderHook(useOverviewViewModel);
  await waitFor(() => expect(result.current.activeTasks).toHaveLength(1));
  vi.mocked(fetchActiveTasks).mockResolvedValue(accepted ? [] : [task]);
  await act(() => result.current.handleCancelTask("WEB"));
  expect(cancelActiveTask).toHaveBeenCalledWith("WEB");
  expect(result.current.activeTasks).toHaveLength(accepted ? 0 : 1);
  expect(accepted ? message.success : message.error).toHaveBeenCalledOnce();
  expect(accepted ? message.error : message.success).not.toHaveBeenCalled();
});

it.each(["task_canceled", "task_timed_out", "task_finished"])(
  "其他页面的 %s 立即移除任务，陈旧响应不能恢复旧任务",
  async (event) => {
    const { result } = renderHook(useOverviewViewModel);
    await waitFor(() => expect(result.current.activeTasks).toHaveLength(1));
    let resolveOld!: (tasks: ActiveTask[]) => void;
    vi.mocked(fetchActiveTasks).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
    );
    let oldRequest!: Promise<void>;
    act(() => {
      oldRequest = result.current.refresh();
    });
    vi.mocked(fetchActiveTasks).mockResolvedValue([]);
    act(() => result.current.handleSSEEvent({ event, data: { task_id: "WEB" } }));
    expect(result.current.activeTasks).toEqual([]);
    await act(async () => {
      resolveOld([task]);
      await oldRequest;
    });
    expect(result.current.activeTasks).toEqual([]);
  },
);
