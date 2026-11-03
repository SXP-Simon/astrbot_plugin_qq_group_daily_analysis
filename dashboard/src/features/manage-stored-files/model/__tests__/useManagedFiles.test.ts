import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useManagedFiles } from "../useManagedFiles";
import { deleteManagedFiles, fetchManagedFiles, fetchManagedPartitions, mutateManagedFile, type ManagedPartition } from "../../../../entities/plugin-data/api/managedFilesApi";

vi.mock("../../../../entities/plugin-data/api/managedFilesApi", () => ({ fetchManagedPartitions: vi.fn(), fetchManagedFiles: vi.fn(), fetchManagedContent: vi.fn(), mutateManagedFile: vi.fn(), deleteManagedFiles: vi.fn() }));
vi.mock("antd", () => ({ message: { success: vi.fn(), error: vi.fn() } }));
const partitions: ManagedPartition[] = ["custom_templates", "config_files"].map(key => ({ key, name: key, directory: key, description: "", impact: "", writable: true, deletable: true, count: 1, size_bytes: 1 }));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchManagedPartitions).mockResolvedValue(partitions);
  vi.mocked(fetchManagedFiles).mockImplementation(async key => ({ items: [{ name: `${key}/report.typ`, revision: key, size_bytes: 1, modified_at: 1, media_type: "text/plain", editable: true, downloadable: true }], total: 1 }));
});

it.each(["save", "delete"])("切换分区后忽略旧 %s 的列表和详情更新", async operation => {
  let finish!: () => void;
  const pending = new Promise<void>(resolve => { finish = resolve; });
  vi.mocked(mutateManagedFile).mockImplementation(async () => { await pending; });
  vi.mocked(deleteManagedFiles).mockImplementation(async () => { await pending; return { deleted: ["custom_templates/report.typ"], failed: [] }; });
  const { result } = renderHook(() => useManagedFiles());
  act(() => result.current.select(partitions[0]));
  await waitFor(() => expect(result.current.files[0]?.name).toBe("custom_templates/report.typ"));
  act(() => result.current.selectFiles(["custom_templates/report.typ"]));
  let action: Promise<unknown>;
  act(() => { action = operation === "save" ? result.current.mutate({ name: "custom_templates/report.typ", operation: "replace", revision: "custom_templates", content_base64: "AA==" }) : result.current.deleteSelected(); });
  act(() => result.current.select(partitions[1]));
  await waitFor(() => expect(result.current.files[0]?.name).toBe("config_files/report.typ"));
  await act(async () => { finish(); await action; });
  expect(result.current.partition?.key).toBe("config_files");
  expect(result.current.files[0].name).toBe("config_files/report.typ");
  expect(result.current.deleteResult).toBeNull();
  expect(vi.mocked(fetchManagedFiles).mock.calls.map(args => args[0])).toEqual(["custom_templates", "config_files"]);
});
