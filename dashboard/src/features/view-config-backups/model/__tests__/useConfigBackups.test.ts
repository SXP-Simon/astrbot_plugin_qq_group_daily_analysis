import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import {
  fetchConfigBackup,
  fetchConfigBackups,
} from "../../../../entities/plugin-data/api/pluginDataApi";
import type { ConfigBackupDetail } from "../../../../entities/plugin-data/model/configBackup";
import { mockConfigBackups } from "../../../../mocks/data/configBackups";
import { useConfigBackups } from "../useConfigBackups";

vi.mock("../../../../entities/plugin-data/api/pluginDataApi", () => ({
  fetchConfigBackups: vi.fn(),
  fetchConfigBackup: vi.fn(),
}));

it("切换备份和关闭窗口后，较早完成的请求不会覆盖当前内容", async () => {
  let finish: (value: ConfigBackupDetail) => void = () => {};
  vi.mocked(fetchConfigBackups).mockResolvedValue(
    mockConfigBackups.map((item) => item.backup),
  );
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
  expect(result.current.detail?.backup.filename).toBe(
    mockConfigBackups[1].backup.filename,
  );
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
