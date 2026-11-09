import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useTemplatePackages } from "@/features/install-template/model/useTemplatePackages";
import { fetchReportTemplates, uninstallTemplate } from "@/entities/report/api/reportApi";
vi.mock("@/entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  uninstallTemplate: vi.fn(),
}));
const groups = [
  { directory: ".", count: 1, size_bytes: 10 },
  { directory: "manual", count: 4, size_bytes: 200 },
];
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "manual", label: "手动模板", is_custom: true, can_uninstall: false },
    { id: "builtin", label: "内置模板" },
  ]);
});
it("模板元数据只补充目录说明，读取失败仍保留已读模板和目录", async () => {
  const { result } = renderHook(() => useTemplatePackages(groups, vi.fn()));
  await waitFor(() =>
    expect(result.current.rows.find((row) => row.directory === "manual")?.template?.label).toBe(
      "手动模板",
    ),
  );
  vi.mocked(fetchReportTemplates).mockRejectedValueOnce(new Error("读取失败"));
  await act(async () => result.current.refresh());
  expect(result.current.rows).toHaveLength(2);
  expect(result.current.rows.find((row) => row.directory === "manual")?.template?.label).toBe(
    "手动模板",
  );
  expect(result.current.error).toBe("读取失败");
});
it("整组移除允许手动模板，验证服务结果，禁止重复提交和删除根目录", async () => {
  const changed = vi.fn();
  const { result } = renderHook(() => useTemplatePackages(groups, changed));
  await waitFor(() => expect(result.current.loading).toBe(false));
  await act(async () => {
    expect(await result.current.uninstall(".")).toBe(false);
  });
  expect(uninstallTemplate).not.toHaveBeenCalled();
  let finish!: (value: { name: string; removed: boolean }) => void;
  vi.mocked(uninstallTemplate).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  let action!: Promise<boolean>;
  act(() => {
    action = result.current.uninstall("manual");
    void result.current.uninstall("manual");
  });
  expect(uninstallTemplate).toHaveBeenCalledTimes(1);
  await act(async () => {
    finish({ name: "other", removed: true });
    expect(await action).toBe(false);
  });
  expect(result.current.actionError).toContain("未移除");
  expect(changed).not.toHaveBeenCalled();
  vi.mocked(uninstallTemplate).mockResolvedValueOnce({ name: "manual", removed: true });
  await act(async () => {
    expect(await result.current.uninstall("manual")).toBe(true);
  });
  expect(changed).toHaveBeenCalledOnce();
  expect(result.current.busy).toBe("");
});
it("卸载后移除请求完成不再触发刷新或旧业务回调", async () => {
  const changed = vi.fn();
  const { result, unmount } = renderHook(() => useTemplatePackages(groups, changed));
  await waitFor(() => expect(result.current.loading).toBe(false));
  let finish!: (value: { name: string; removed: boolean }) => void;
  vi.mocked(uninstallTemplate).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  let action!: Promise<boolean>;
  act(() => {
    action = result.current.uninstall("manual");
  });
  unmount();
  await act(async () => {
    finish({ name: "manual", removed: true });
    expect(await action).toBe(false);
  });
  expect(changed).not.toHaveBeenCalled();
  expect(fetchReportTemplates).toHaveBeenCalledTimes(1);
});
