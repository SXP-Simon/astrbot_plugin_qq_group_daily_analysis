import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchReportHistory } from "@/entities/report/api/reportApi";
import { fetchGroupSessions } from "@/entities/group/api/groupApi";
import type { ReportItem } from "@/entities/report/model/types";
import { useReportsViewModel } from "@/pages/reports/model/useReportsViewModel";

vi.mock("@/entities/report/api/reportApi", () => ({
  fetchReportHistory: vi.fn(),
  fetchReportContent: vi.fn(),
}));
vi.mock("@/entities/group/api/groupApi", () => ({ fetchGroupSessions: vi.fn() }));
const first: ReportItem = {
  filename: "example-a.png",
  size_bytes: 100,
  modified_at: 200,
  group_id: "123",
  group_name: "示例群聊",
  platform: "telegram",
};
const second: ReportItem = { ...first, filename: "example-b.html", modified_at: 100 };
beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchReportHistory).mockResolvedValue({ items: [first, second], total: 52 });
  vi.mocked(fetchGroupSessions).mockResolvedValue([]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("搜索防抖，筛选变化立即废弃旧页响应，分页只发出一次请求", async () => {
  let finish!: (value: Awaited<ReturnType<typeof fetchReportHistory>>) => void;
  vi.mocked(fetchReportHistory).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSearch("旧"));
  await act(async () => finish({ items: [first], total: 1 }));
  expect(result.current.reports).toHaveLength(0);
  act(() => result.current.setSearch(" example "));
  await act(async () => vi.advanceTimersByTimeAsync(249));
  expect(fetchReportHistory).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(fetchReportHistory).toHaveBeenLastCalledWith({
    limit: 20,
    offset: 0,
    group_id: undefined,
    search: "example",
    start_time: undefined,
    end_time: undefined,
    sort_order: "desc",
  });
  act(() => result.current.handlePageChange(2, 20));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenCalledTimes(3);
  expect(fetchReportHistory).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 }));
  act(() => result.current.setSelectedGroup("123"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenLastCalledWith(
    expect.objectContaining({ offset: 0, group_id: "123" }),
  );
});

it("日期和排序传给后端并回到第一页，展示服务端返回的全局总数", async () => {
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.handlePageChange(2));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchReportHistory).mockResolvedValueOnce({ items: [second, first], total: 52 });
  act(() => result.current.setSortOrder("asc"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.page).toBe(1);
  expect(result.current.reports).toEqual([second, first]);
  expect(fetchReportHistory).toHaveBeenLastCalledWith(
    expect.objectContaining({ sort_order: "asc", offset: 0 }),
  );
  vi.mocked(fetchReportHistory).mockResolvedValueOnce({ items: [second], total: 1 });
  act(() => result.current.setDateRange([100, 100]));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenLastCalledWith(
    expect.objectContaining({ start_time: 100, end_time: 100 }),
  );
  expect(result.current.total).toBe(1);
  expect(result.current.reports).toEqual([second]);
});

it("通知更新不请求或跳页，主动刷新保留页码，刷新中的新通知不会丢失", async () => {
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.handlePageChange(2));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  const calls = vi.mocked(fetchReportHistory).mock.calls.length;
  act(() => result.current.markUpdated());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenCalledTimes(calls);
  expect(result.current.page).toBe(2);
  expect(result.current.hasUpdates).toBe(true);
  act(() => result.current.refresh(false));
  act(() => result.current.markUpdated());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.hasUpdates).toBe(true);
  expect(result.current.page).toBe(2);
});

it("翻页失败保留旧页并标明来源，刷新保留筛选，页数减少时自动回到最后一页", async () => {
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchReportHistory).mockRejectedValueOnce(new Error("请求失败"));
  act(() => result.current.handlePageChange(3));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.error).toContain("请求失败");
  expect(result.current.loadedPage).toBe(1);
  expect(result.current.page).toBe(3);
  expect(result.current.reports).toHaveLength(2);
  vi.mocked(fetchReportHistory).mockResolvedValue({ items: [second], total: 21 });
  vi.mocked(fetchGroupSessions).mockRejectedValueOnce(new Error("群聊暂不可读"));
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(result.current.page).toBe(2);
  expect(result.current.loadedPage).toBe(2);
  expect(result.current.reports).toEqual([second]);
  expect(result.current.error).toBe("");
  expect(result.current.groupsError).toContain("群聊暂不可读");
  act(() => result.current.refresh(false, true));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.page).toBe(1);
  expect(result.current.groupsError).toBe("");
});

it("卸载清除搜索定时器，迟到失败不再写回或发起请求", async () => {
  let fail!: (error: Error) => void;
  vi.mocked(fetchReportHistory).mockReturnValueOnce(
    new Promise((_resolve, reject) => {
      fail = reject;
    }),
  );
  const { result, unmount } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSearch("新的搜索"));
  unmount();
  await act(async () => {
    fail(new Error("迟到失败"));
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(fetchReportHistory).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});

it("平台变更清空群聊，群聊选择携带平台身份", async () => {
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSelectedGroup("same", "telegram"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: "same", platform: "telegram" }),
  );
  act(() => result.current.setSelectedPlatform(""));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchReportHistory).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: undefined, platform: "" }),
  );
});

it("连续切页立即更新目标，旧页成功或失败都不能覆盖最终选择", async () => {
  vi.mocked(fetchReportHistory).mockResolvedValueOnce({ items: [first], total: 80 });
  const { result } = renderHook(useReportsViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  let resolve!: (value: Awaited<ReturnType<typeof fetchReportHistory>>) => void;
  let reject!: (error: Error) => void;
  vi.mocked(fetchReportHistory)
    .mockReturnValueOnce(
      new Promise((done, fail) => {
        resolve = done;
        reject = fail;
      }),
    )
    .mockResolvedValueOnce({ items: [{ ...first, filename: "page-3.png" }], total: 80 });
  act(() => result.current.handlePageChange(2, 20));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.page).toBe(2);
  expect(result.current.total).toBe(80);
  expect(result.current.loading).toBe(true);
  act(() => result.current.handlePageChange(3, 20));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => resolve({ items: [first], total: 1 }));
  expect(result.current.page).toBe(3);
  expect(result.current.reports[0].filename).toBe("page-3.png");
  expect(result.current.total).toBe(80);
  expect(result.current.loading).toBe(false);

  vi.mocked(fetchReportHistory)
    .mockReturnValueOnce(
      new Promise((_, fail) => {
        reject = fail;
      }),
    )
    .mockResolvedValueOnce({ items: [first], total: 80 });
  act(() => result.current.handlePageChange(2, 20));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.handlePageChange(1, 20));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => reject(new Error("迟到的失败")));
  expect(result.current.page).toBe(1);
  expect(result.current.error).toBe("");
  expect(result.current.loading).toBe(false);
});
