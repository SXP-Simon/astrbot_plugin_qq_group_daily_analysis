import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useStoredRecords } from "../useStoredRecords";
import { fetchManagedRecords } from "../../../../entities/plugin-data/api/managedRecordsApi";
vi.mock("../../../../entities/plugin-data/api/managedRecordsApi", () => ({
  fetchManagedRecords: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const entry = {
  locator: { kind: "history", key: "analysis_string-id_2026-11-07" },
  name: "示例存档",
  size_bytes: 0,
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
it("切换筛选立即清除旧行、回第一页，迟到响应不覆盖新结果", async () => {
  vi.mocked(fetchManagedRecords).mockResolvedValueOnce({ items: [entry], total: 60 });
  const { result } = renderHook(() => useStoredRecords());
  await waitFor(() => expect(result.current.items).toHaveLength(1));
  const old = deferred<Awaited<ReturnType<typeof fetchManagedRecords>>>();
  vi.mocked(fetchManagedRecords).mockReturnValueOnce(old.promise);
  act(() => result.current.setPage(3));
  expect(result.current.items).toEqual([]);
  vi.mocked(fetchManagedRecords).mockResolvedValueOnce({
    items: [{ ...entry, name: "匹配存档" }],
    total: 1,
  });
  act(() => result.current.setSearch(" string-id "));
  await waitFor(() => expect(result.current.items[0]?.name).toBe("匹配存档"));
  expect(result.current.page).toBe(1);
  expect(fetchManagedRecords).toHaveBeenLastCalledWith("history", "string-id", 1);
  await act(async () => old.resolve({ items: [entry], total: 60 }));
  expect(result.current.total).toBe(1);
  expect(result.current.items[0]?.name).toBe("匹配存档");
});
it("删除导致越界后重新读取最后一页，刷新失败保留当前行", async () => {
  vi.mocked(fetchManagedRecords).mockResolvedValueOnce({ items: [entry], total: 41 });
  const { result } = renderHook(() => useStoredRecords());
  await waitFor(() => expect(result.current.total).toBe(41));
  vi.mocked(fetchManagedRecords)
    .mockResolvedValueOnce({ items: [], total: 20 })
    .mockResolvedValueOnce({ items: [entry], total: 20 });
  act(() => result.current.setPage(3));
  await waitFor(() => expect(fetchManagedRecords).toHaveBeenLastCalledWith("history", "", 1));
  await waitFor(() => expect(result.current.items).toEqual([entry]));
  expect(result.current.page).toBe(1);
  vi.mocked(fetchManagedRecords).mockRejectedValueOnce(new Error("网络断开"));
  await act(async () => result.current.refresh());
  expect(result.current.items).toEqual([entry]);
  expect(result.current.error).toBe("网络断开");
  vi.mocked(fetchManagedRecords).mockResolvedValueOnce({ items: [], total: 0 });
  await act(async () => result.current.refresh());
  expect(result.current.items).toEqual([]);
  expect(result.current.error).toBe("");
});
it("旧回调刷新也只查询当前类型，卸载后丢弃返回值", async () => {
  vi.mocked(fetchManagedRecords).mockResolvedValue({ items: [entry], total: 1 });
  const { result, unmount } = renderHook(() => useStoredRecords());
  await waitFor(() => expect(result.current.total).toBe(1));
  const refresh = result.current.refresh;
  act(() => result.current.setKind("avatar"));
  await act(async () => refresh());
  expect(fetchManagedRecords).toHaveBeenLastCalledWith("avatar", "", 1);
  const pending = deferred<Awaited<ReturnType<typeof fetchManagedRecords>>>();
  vi.mocked(fetchManagedRecords).mockReturnValueOnce(pending.promise);
  let request!: Promise<void>;
  act(() => {
    request = result.current.refresh();
  });
  unmount();
  await act(async () => {
    pending.resolve({ items: [], total: 0 });
    await request;
  });
  expect(result.current.total).toBe(1);
});
it("切换限定分区同步类型并清空搜索，非法页码回到首页", async () => {
  vi.mocked(fetchManagedRecords).mockResolvedValue({ items: [], total: 100 });
  const { result, rerender } = renderHook(
    ({ kind }: { kind: "history" | "avatar" }) => useStoredRecords(kind),
    { initialProps: { kind: "history" as "history" | "avatar" } },
  );
  await waitFor(() => expect(result.current.total).toBe(100));
  act(() => result.current.setSearch("old"));
  await waitFor(() => expect(fetchManagedRecords).toHaveBeenLastCalledWith("history", "old", 1));
  rerender({ kind: "avatar" });
  await waitFor(() => expect(fetchManagedRecords).toHaveBeenLastCalledWith("avatar", "", 1));
  act(() => result.current.setPage(2));
  await waitFor(() => expect(result.current.page).toBe(2));
  act(() => result.current.setPage(NaN));
  await waitFor(() => expect(result.current.page).toBe(1));
});
