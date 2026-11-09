import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchConfigBackup, fetchConfigBackups } from "@/entities/plugin-data/api/pluginDataApi";
import type { ConfigBackupDetail } from "@/entities/plugin-data/model/configBackup";
import { mockConfigBackups } from "@/mocks/data/configBackups";
import { useConfigBackups } from "@/features/view-config-backups/model/useConfigBackups";

vi.mock("@/entities/plugin-data/api/pluginDataApi", () => ({
  fetchConfigBackups: vi.fn(),
  fetchConfigBackup: vi.fn(),
}));

beforeEach(() => vi.resetAllMocks());

it("返回了其他文件的内容时不展示，刷新后清除选择并回到第一页", async () => {
  vi.mocked(fetchConfigBackups).mockResolvedValue(mockConfigBackups.map((item) => item.backup));
  vi.mocked(fetchConfigBackup).mockResolvedValue(mockConfigBackups[1]);
  const { result } = renderHook(useConfigBackups);
  await act(async () => result.current.load());
  act(() => result.current.setPage(2));
  await act(async () => result.current.select(mockConfigBackups[0].backup.filename));
  expect(result.current.detail).toBeNull();
  expect(result.current.detailError).toContain("这份备份暂时无法打开");
  expect(result.current.detailLoading).toBe(false);
  await act(async () => result.current.load());
  expect(result.current.page).toBe(1);
  expect(result.current.selectedFilename).toBeNull();
  expect(result.current.detailError).toBe("");
});

it("关闭后重开只接收新列表，迟到的旧列表不能替换当前文件", async () => {
  let finish: (value: (typeof mockConfigBackups)[number]["backup"][]) => void = () => {};
  vi.mocked(fetchConfigBackups)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce([mockConfigBackups[1].backup]);
  const { result } = renderHook(useConfigBackups);
  let first: Promise<void>;
  act(() => {
    first = result.current.load();
  });
  act(() => result.current.close());
  await act(async () => result.current.load());
  await act(async () => {
    finish([mockConfigBackups[0].backup]);
    await first;
  });
  expect(result.current.items).toEqual([mockConfigBackups[1].backup]);
  expect(result.current.open).toBe(true);
  expect(result.current.loading).toBe(false);
});

it("切换备份和关闭窗口后，较早完成的请求不会覆盖当前内容", async () => {
  let finish: (value: ConfigBackupDetail) => void = () => {};
  vi.mocked(fetchConfigBackups).mockResolvedValue(mockConfigBackups.map((item) => item.backup));
  vi.mocked(fetchConfigBackup)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce(mockConfigBackups[1]);
  const { result } = renderHook(useConfigBackups);
  await act(async () => {
    await result.current.load();
  });
  let first: Promise<void>;
  act(() => {
    first = result.current.select(mockConfigBackups[0].backup.filename);
  });
  await act(async () => {
    await result.current.select(mockConfigBackups[1].backup.filename);
  });
  await act(async () => {
    finish(mockConfigBackups[0]);
    await first;
  });
  expect(result.current.detail?.backup.filename).toBe(mockConfigBackups[1].backup.filename);
  vi.mocked(fetchConfigBackup).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  act(() => {
    first = result.current.select(mockConfigBackups[0].backup.filename);
  });
  act(() => result.current.close());
  await act(async () => {
    finish(mockConfigBackups[0]);
    await first;
  });
  expect(result.current.detail).toBeNull();
  expect(result.current.open).toBe(false);
});
