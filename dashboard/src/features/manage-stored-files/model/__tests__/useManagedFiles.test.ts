import { act, renderHook, waitFor } from "@testing-library/react";
import { useLayoutEffect } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { useManagedFiles } from "../useManagedFiles";
import {
  deleteManagedFiles,
  fetchManagedContent,
  fetchManagedFiles,
  fetchManagedPartitions,
  mutateManagedFile,
  type ManagedPartition,
} from "../../../../entities/plugin-data/api/managedFilesApi";

vi.mock("../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedPartitions: vi.fn(),
  fetchManagedFiles: vi.fn(),
  fetchManagedContent: vi.fn(),
  mutateManagedFile: vi.fn(),
  deleteManagedFiles: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const partitions: ManagedPartition[] = ["custom_templates", "config_files"].map((key) => ({
  key,
  name: key,
  directory: key,
  description: "",
  impact: "",
  writable: true,
  deletable: true,
  count: 1,
  size_bytes: 1,
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchManagedPartitions).mockResolvedValue(partitions);
  vi.mocked(fetchManagedFiles).mockImplementation(async (key) => ({
    items: [
      {
        name: `${key}/report.typ`,
        revision: key,
        size_bytes: 1,
        modified_at: 1,
        media_type: "text/plain",
        editable: true,
        downloadable: true,
      },
    ],
    total: 1,
  }));
});

it("打开分区的首次提交就是加载态，慢请求不会先暴露空列表", async () => {
  let finish!: (value: { items: []; total: number }) => void;
  vi.mocked(fetchManagedFiles).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const observed: boolean[] = [];
  const { result, unmount } = renderHook(() => {
    const vm = useManagedFiles();
    useLayoutEffect(() => {
      if (vm.partition) observed.push(vm.loading);
    }, [vm.partition, vm.loading]);
    return vm;
  });
  act(() => result.current.select(partitions[1]));
  expect(observed).toEqual([true]);
  expect(result.current.loading).toBe(true);
  await act(async () => finish({ items: [], total: 0 }));
  expect(result.current.loading).toBe(false);
  expect(observed).toEqual([true, false]);
  act(() => result.current.select(null));
  expect(result.current.loading).toBe(false);
  unmount();
});

it("上传主题素材按固定清单命名，并读取现有文件修订号以安全替换", async () => {
  const resource = { ...partitions[0], key: "template_resources" };
  const name = "ATRI/paper.png";
  vi.mocked(fetchManagedFiles).mockResolvedValue({
    items: [
      {
        name,
        revision: "existing",
        size_bytes: 10,
        modified_at: 1,
        media_type: "image/png",
        editable: false,
        downloadable: true,
      },
    ],
    total: 1,
  });
  const { result } = renderHook(() => useManagedFiles());
  act(() => result.current.select(resource));
  await act(async () => {
    await result.current.prepareUpload(new File([new Uint8Array(20)], "upstream.png"), false, name);
  });
  expect(result.current.editor).toMatchObject({
    name,
    revision: "existing",
    encoded: expect.any(String),
  });
  expect(fetchManagedFiles).toHaveBeenCalledWith("template_resources", name, 1);
});

it.each(["save", "delete"])("切换分区后忽略旧 %s 的列表和详情更新", async (operation) => {
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  vi.mocked(mutateManagedFile).mockImplementation(async () => {
    await pending;
  });
  vi.mocked(deleteManagedFiles).mockImplementation(async () => {
    await pending;
    return { deleted: ["custom_templates/report.typ"], failed: [] };
  });
  const { result } = renderHook(() => useManagedFiles());
  act(() => result.current.select(partitions[0]));
  await waitFor(() => expect(result.current.files[0]?.name).toBe("custom_templates/report.typ"));
  act(() => result.current.selectFiles(["custom_templates/report.typ"]));
  let action: Promise<unknown>;
  act(() => {
    action =
      operation === "save"
        ? result.current.mutate({
            name: "custom_templates/report.typ",
            operation: "replace",
            revision: "custom_templates",
            content_base64: "AA==",
          })
        : result.current.deleteSelected();
  });
  act(() => result.current.select(partitions[1]));
  await waitFor(() => expect(result.current.files[0]?.name).toBe("config_files/report.typ"));
  await act(async () => {
    finish();
    await action;
  });
  expect(result.current.partition?.key).toBe("config_files");
  expect(result.current.files[0].name).toBe("config_files/report.typ");
  expect(result.current.deleteResult).toBeNull();
  expect(vi.mocked(fetchManagedFiles).mock.calls.map((args) => args[0])).toEqual([
    "custom_templates",
    "config_files",
  ]);
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
it("概览旧响应不覆盖最新结果或提前解除读取状态，失败保留已有分区", async () => {
  const old = deferred<ManagedPartition[]>();
  const current = deferred<ManagedPartition[]>();
  vi.mocked(fetchManagedPartitions)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  const { result } = renderHook(useManagedFiles);
  expect(result.current.overviewLoading).toBe(true);
  act(() => {
    void result.current.refresh();
  });
  await act(async () => old.resolve([]));
  expect(result.current.overviewLoading).toBe(true);
  await act(async () => current.resolve(partitions));
  expect(result.current.partitions).toEqual(partitions);
  expect(result.current.overviewLoading).toBe(false);
  vi.mocked(fetchManagedPartitions).mockRejectedValueOnce(new Error("暂时无法读取概览"));
  await act(async () => result.current.refresh());
  expect(result.current.partitions).toEqual(partitions);
  expect(result.current.error).toBe("暂时无法读取概览");
  expect(result.current.overviewLoading).toBe(false);
});
it("同步阻止重复写入，失败保留编辑稿与修订号", async () => {
  const pending = deferred<void>();
  vi.mocked(mutateManagedFile).mockReturnValueOnce(pending.promise);
  const { result } = renderHook(useManagedFiles);
  act(() => result.current.select(partitions[0]));
  act(() =>
    result.current.setEditor({ name: "custom_templates/report.typ", text: "修订", revision: "v1" }),
  );
  act(() => {
    void result.current.saveEditor();
    void result.current.saveEditor();
  });
  expect(mutateManagedFile).toHaveBeenCalledTimes(1);
  expect(mutateManagedFile).toHaveBeenCalledWith(
    expect.objectContaining({ revision: "v1", operation: "replace" }),
  );
  await act(async () => pending.reject(new Error("修订已过期")));
  expect(result.current.actionError).toBe("修订已过期");
  expect(result.current.editor?.text).toBe("修订");
  expect(result.current.busy).toBe(false);
});
it("旧详情完成不清除新分区的操作锁，返回文件名必须匹配", async () => {
  const first = deferred<Awaited<ReturnType<typeof fetchManagedContent>>>();
  const second = deferred<Awaited<ReturnType<typeof fetchManagedContent>>>();
  vi.mocked(fetchManagedContent)
    .mockReturnValueOnce(first.promise)
    .mockReturnValueOnce(second.promise);
  const { result } = renderHook(useManagedFiles);
  act(() => result.current.select(partitions[0]));
  act(() => {
    void result.current.inspect("old.typ");
  });
  act(() => result.current.select(partitions[1]));
  act(() => {
    void result.current.inspect("new.png");
  });
  await act(async () =>
    first.resolve({
      name: "old.typ",
      revision: "v1",
      content_base64: "",
      text: "old",
      media_type: "text/plain",
    }),
  );
  expect(result.current.busy).toBe(true);
  expect(result.current.content).toBeNull();
  await act(async () =>
    second.resolve({
      name: "wrong.png",
      revision: "v2",
      content_base64: "",
      text: null,
      media_type: "image/png",
    }),
  );
  expect(result.current.content).toBeNull();
  expect(result.current.busy).toBe(false);
});
it("读取替换文件期间不能保存，取消编辑后不恢复上传草稿", async () => {
  const { result } = renderHook(useManagedFiles);
  act(() => result.current.select(partitions[0]));
  act(() =>
    result.current.setEditor({ name: "report.typ", text: "", encoded: "old", revision: "v1" }),
  );
  let reading!: Promise<void>;
  act(() => {
    reading = result.current.prepareUpload(new File(["new"], "new.typ"), true);
    void result.current.saveEditor();
  });
  expect(result.current.uploading).toBe(true);
  await act(async () => result.current.saveEditor());
  expect(mutateManagedFile).not.toHaveBeenCalled();
  act(() => result.current.cancelEditor());
  await act(async () => reading);
  expect(result.current.editor).toBeNull();
  expect(result.current.uploading).toBe(false);
});

it("记录减少时修正最后页，旧筛选的刷新回调不能重新查询旧范围", async () => {
  const { result } = renderHook(useManagedFiles);
  act(() => result.current.select(partitions[0]));
  await waitFor(() => expect(result.current.loading).toBe(false));
  const oldLoad = result.current.load;
  act(() => result.current.searchFiles("new"));
  await waitFor(() =>
    expect(fetchManagedFiles).toHaveBeenLastCalledWith("custom_templates", "new", 1, "", ""),
  );
  const calls = vi.mocked(fetchManagedFiles).mock.calls.length;
  await act(async () => oldLoad());
  expect(fetchManagedFiles).toHaveBeenCalledTimes(calls);
  act(() => result.current.setPage(3));
  await waitFor(() => expect(result.current.page).toBe(1));
  await waitFor(() =>
    expect(fetchManagedFiles).toHaveBeenLastCalledWith("custom_templates", "new", 1, "", ""),
  );
});

it("删除固定确认时的修订号，失败保留原因且跨分区目标被拒绝", async () => {
  const { result } = renderHook(useManagedFiles);
  act(() => result.current.select(partitions[0]));
  await waitFor(() => expect(result.current.files.length).toBe(1));
  const targets = [...result.current.files];
  vi.mocked(deleteManagedFiles).mockRejectedValueOnce(new Error("修订冲突"));
  let ok: boolean | undefined;
  await act(async () => {
    ok = await result.current.deleteSelected(targets, "custom_templates");
  });
  expect(ok).toBe(false);
  expect(result.current.actionError).toBe("修订冲突");
  expect(deleteManagedFiles).toHaveBeenCalledWith("custom_templates", [
    { name: targets[0].name, revision: targets[0].revision },
  ]);
  act(() => result.current.select(partitions[1]));
  await act(async () => {
    ok = await result.current.deleteSelected(targets, "custom_templates");
  });
  expect(ok).toBe(false);
  expect(deleteManagedFiles).toHaveBeenCalledTimes(1);
});
