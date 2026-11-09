import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useRecordSelection, recordKey } from "@/pages/plugin-data/model/useRecordSelection";
import {
  fetchManagedRecord,
  mutateManagedRecord,
  type RecordLocator,
} from "@/entities/plugin-data/api/managedRecordsApi";
vi.mock("@/entities/plugin-data/api/managedRecordsApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/plugin-data/api/managedRecordsApi")>()),
  fetchManagedRecord: vi.fn(),
  mutateManagedRecord: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const records: RecordLocator[] = ["a", "b"].map((batch_id) => ({
  kind: "batch",
  group_id: "g",
  batch_id,
}));
it("批量操作防重入，成功移出选择而拒绝项保留，逐项使用真实 revision", async () => {
  let finish!: () => void;
  vi.mocked(fetchManagedRecord).mockImplementation(async (locator) => ({
    locator,
    revision: `rev-${locator.batch_id}`,
    data: {},
  }));
  vi.mocked(mutateManagedRecord)
    .mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    )
    .mockRejectedValueOnce(new Error("群任务正在运行"));
  const changed = vi.fn();
  const { result } = renderHook(() => useRecordSelection(records, changed));
  act(() => result.current.select(records.map(recordKey)));
  let request!: Promise<void>;
  await act(async () => {
    request = result.current.remove();
    void result.current.remove();
  });
  expect(fetchManagedRecord).toHaveBeenCalledTimes(1);
  await act(async () => {
    finish();
    await request;
  });
  expect(mutateManagedRecord).toHaveBeenCalledWith({
    locator: records[0],
    revision: "rev-a",
    operation: "delete",
  });
  expect(result.current.selected).toEqual([records[1]]);
  expect(result.current.result).toMatchObject({
    deleted: 1,
    failed: [{ message: "群任务正在运行" }],
  });
  expect(changed).toHaveBeenCalledTimes(1);
});
it("清除选择或离开页面后旧操作不写回其他群的结果", async () => {
  let finish!: () => void;
  vi.mocked(fetchManagedRecord).mockImplementation(async (locator) => ({
    locator,
    revision: "rev",
    data: {},
  }));
  vi.mocked(mutateManagedRecord).mockImplementation(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  const changed = vi.fn();
  const { result, unmount } = renderHook(() => useRecordSelection(records, changed));
  let request!: Promise<void>;
  await act(async () => {
    request = result.current.remove([records[0]]);
  });
  act(() => result.current.clear());
  await act(async () => {
    finish();
    await request;
  });
  expect(result.current.result).toBeNull();
  expect(changed).not.toHaveBeenCalled();
  await act(async () => {
    request = result.current.remove([records[1]]);
  });
  unmount();
  await act(async () => {
    finish();
    await request;
  });
  expect(changed).not.toHaveBeenCalled();
});
