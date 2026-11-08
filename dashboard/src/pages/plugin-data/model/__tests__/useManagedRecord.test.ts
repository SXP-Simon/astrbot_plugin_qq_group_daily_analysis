import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import {
  fetchManagedRecord,
  mutateManagedRecord,
} from "../../../../entities/plugin-data/api/managedRecordsApi";
import { useManagedRecord } from "../useManagedRecord";

vi.mock("../../../../entities/plugin-data/api/managedRecordsApi", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("../../../../entities/plugin-data/api/managedRecordsApi")
  >()),
  fetchManagedRecord: vi.fn(),
  mutateManagedRecord: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

it("头像下载为图片并清理缓存键中的路径字符，不导出 JSON 包装", async () => {
  const locator = { kind: "avatar", key: "onebot:123456" };
  const uri = "data:image/png;base64,iVBORw0KGgo=";
  vi.mocked(fetchManagedRecord).mockResolvedValue({
    locator,
    revision: "v1",
    data: { data_uri: uri },
  });
  let downloaded = { href: "", name: "" };
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloaded = { href: this.href, name: this.download };
  });
  const { result } = renderHook(() => useManagedRecord(locator, vi.fn(), vi.fn()));
  await waitFor(() => expect(result.current.record).not.toBeNull());
  act(() => result.current.download());
  expect(downloaded).toEqual({ href: uri, name: "avatar-onebot_123456.png" });
});

const first = { kind: "history", key: "first" };
const second = { kind: "history", key: "second" };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
it("切换记录、关闭和重试时只采纳当前读取结果", async () => {
  const old = deferred<Awaited<ReturnType<typeof fetchManagedRecord>>>();
  vi.mocked(fetchManagedRecord)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce({ locator: second, revision: "v2", data: { unknown: [false, 0] } });
  const { result, rerender } = renderHook(
    ({ locator }) => useManagedRecord(locator, vi.fn(), vi.fn()),
    { initialProps: { locator: first } },
  );
  rerender({ locator: second });
  await waitFor(() => expect(result.current.record?.revision).toBe("v2"));
  await act(async () => old.resolve({ locator: first, revision: "v1", data: {} }));
  expect(result.current.record?.locator).toEqual(second);
  vi.mocked(fetchManagedRecord).mockRejectedValueOnce(new Error("网络断开"));
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.error).toBe("网络断开"));
  vi.mocked(fetchManagedRecord).mockResolvedValueOnce({
    locator: second,
    revision: "v3",
    data: null,
  });
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.text).toBe("null"));
});
it("拒绝不匹配的详情，关闭后旧读取不写回", async () => {
  vi.mocked(fetchManagedRecord).mockResolvedValueOnce({
    locator: second,
    revision: "v2",
    data: {},
  });
  const { result, rerender } = renderHook(
    ({ locator }: { locator: typeof first | null }) => useManagedRecord(locator, vi.fn(), vi.fn()),
    { initialProps: { locator: first as typeof first | null } },
  );
  await waitFor(() => expect(result.current.error).toContain("不一致"));
  expect(result.current.record).toBeNull();
  const read = deferred<Awaited<ReturnType<typeof fetchManagedRecord>>>();
  vi.mocked(fetchManagedRecord).mockReturnValueOnce(read.promise);
  act(() => result.current.retry());
  rerender({ locator: null });
  await act(async () => read.resolve({ locator: first, revision: "v1", data: {} }));
  expect(result.current.record).toBeNull();
  expect(result.current.busy).toBe(false);
});
it("保存使用原修订号、阻止重复提交，失败保留编辑稿并允许重试", async () => {
  vi.mocked(fetchManagedRecord).mockResolvedValue({
    locator: first,
    revision: "v1",
    data: { value: 1 },
  });
  const changed = vi.fn(),
    close = vi.fn();
  const { result } = renderHook(() => useManagedRecord(first, changed, close));
  await waitFor(() => expect(result.current.busy).toBe(false));
  act(() => {
    result.current.setEditing(true);
    result.current.setText('{"value":2}');
  });
  const save = deferred<void>();
  vi.mocked(mutateManagedRecord).mockReturnValueOnce(save.promise);
  act(() => {
    void result.current.save("replace");
    void result.current.save("replace");
  });
  expect(mutateManagedRecord).toHaveBeenCalledTimes(1);
  expect(mutateManagedRecord).toHaveBeenCalledWith({
    locator: first,
    data: { value: 2 },
    operation: "replace",
    revision: "v1",
  });
  await act(async () => save.reject(new Error("记录已更新，请重新读取")));
  expect(result.current.text).toBe('{"value":2}');
  expect(result.current.editing).toBe(true);
  expect(result.current.error).toContain("记录已更新");
  expect(close).not.toHaveBeenCalled();
  vi.mocked(mutateManagedRecord).mockResolvedValueOnce(undefined);
  await act(async () => {
    expect(await result.current.save("replace")).toBe(true);
  });
  expect(close).toHaveBeenCalledOnce();
  expect(changed).toHaveBeenCalledOnce();
});
it("旧记录保存完成不关闭新记录，也不清除新请求的忙碌状态", async () => {
  vi.mocked(fetchManagedRecord).mockResolvedValueOnce({ locator: first, revision: "v1", data: {} });
  const changed = vi.fn(),
    close = vi.fn();
  const { result, rerender } = renderHook(
    ({ locator }) => useManagedRecord(locator, changed, close),
    { initialProps: { locator: first } },
  );
  await waitFor(() => expect(result.current.record).not.toBeNull());
  const saving = deferred<void>(),
    reading = deferred<Awaited<ReturnType<typeof fetchManagedRecord>>>();
  vi.mocked(mutateManagedRecord).mockReturnValueOnce(saving.promise);
  act(() => {
    void result.current.save("delete");
  });
  vi.mocked(fetchManagedRecord).mockReturnValueOnce(reading.promise);
  rerender({ locator: second });
  await act(async () => saving.resolve());
  expect(close).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
  expect(result.current.busy).toBe(true);
  await act(async () => reading.resolve({ locator: second, revision: "v2", data: {} }));
  expect(result.current.record?.locator).toEqual(second);
});
it("导入校验类型并原样保留 null 数据，卸载后不回调", async () => {
  const changed = vi.fn(),
    close = vi.fn();
  const { result, unmount } = renderHook(() => useManagedRecord(null, changed, close, "history"));
  act(() => result.current.setText("{"));
  await act(async () => {
    await result.current.save("create");
  });
  expect(result.current.error).toContain("JSON 格式不正确");
  expect(mutateManagedRecord).not.toHaveBeenCalled();
  act(() => result.current.setText('{"data":{}}'));
  await act(async () => {
    await result.current.save("create");
  });
  expect(result.current.error).toContain("包含有效的 locator 和 data");
  expect(mutateManagedRecord).not.toHaveBeenCalled();
  act(() =>
    result.current.setText(
      JSON.stringify({ locator: { kind: "batch", group_id: "g", batch_id: "b" }, data: {} }),
    ),
  );
  await act(async () => {
    await result.current.save("create");
  });
  expect(result.current.error).toContain("导入类型");
  act(() => result.current.setText(JSON.stringify({ locator: first, data: null })));
  const saving = deferred<void>();
  vi.mocked(mutateManagedRecord).mockReturnValueOnce(saving.promise);
  act(() => {
    void result.current.save("create");
  });
  expect(mutateManagedRecord).toHaveBeenLastCalledWith({
    locator: first,
    data: null,
    operation: "create",
    revision: undefined,
  });
  unmount();
  await act(async () => saving.resolve());
  expect(close).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
});
