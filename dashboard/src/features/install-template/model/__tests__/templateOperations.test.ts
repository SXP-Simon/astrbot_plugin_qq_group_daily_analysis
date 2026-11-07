import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useTemplateInstall } from "../useTemplateInstall";
import { useTemplateRemoval } from "../useTemplateRemoval";
import {
  fetchReportTemplates,
  installTemplateFromUrl,
  installTemplateFromFile,
  uninstallTemplate,
  type TemplateInstallResult,
} from "../../../../entities/report/api/reportApi";

vi.mock("../../../../entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  installTemplateFromUrl: vi.fn(),
  installTemplateFromFile: vi.fn(),
  uninstallTemplate: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
const installed: TemplateInstallResult = {
  name: "sample",
  label: "示例模板",
  files: ["report.typ"],
  has_image: false,
  has_html: false,
  has_typst: true,
};
const custom = {
  id: "sample",
  label: "示例模板",
  can_uninstall: true,
  is_custom: true,
  has_typst: true,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    custom,
    { id: "builtin", label: "内置", can_uninstall: false },
  ]);
  vi.mocked(installTemplateFromUrl).mockResolvedValue(installed);
  vi.mocked(installTemplateFromFile).mockResolvedValue(installed);
  vi.mocked(uninstallTemplate).mockResolvedValue({ name: "sample", removed: true });
});

it("安装校验与重复提交：失败保留输入，成功再通知父组件", async () => {
  const close = vi.fn(),
    changed = vi.fn();
  const { result } = renderHook(() => useTemplateInstall(true, close, changed));
  await act(async () => result.current.install());
  expect(result.current.error).toContain("GitHub");
  expect(installTemplateFromUrl).not.toHaveBeenCalled();
  act(() => {
    result.current.setUrl(" https://github.com/example/repo ");
    result.current.setName(" sample ");
  });
  let reject!: (reason: Error) => void;
  vi.mocked(installTemplateFromUrl).mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  let action!: Promise<void>;
  act(() => {
    action = result.current.install();
    void result.current.install();
    result.current.close();
  });
  expect(installTemplateFromUrl).toHaveBeenCalledTimes(1);
  expect(close).not.toHaveBeenCalled();
  await act(async () => {
    reject(new Error("下载超时"));
    await action;
  });
  expect(result.current.url).toContain("example/repo");
  expect(result.current.names.url).toBe(" sample ");
  expect(result.current.error).toBe("下载超时");
  await act(async () => result.current.install());
  expect(changed).toHaveBeenCalledWith(installed);
  expect(close).toHaveBeenCalledOnce();
  expect(installTemplateFromUrl).toHaveBeenLastCalledWith({
    repo_url: "https://github.com/example/repo",
    name: "sample",
  });
});

it("外部关闭再打开后，旧安装请求不能关闭新窗口或触发回调", async () => {
  const close = vi.fn(),
    changed = vi.fn();
  let finish!: (value: TemplateInstallResult) => void;
  vi.mocked(installTemplateFromUrl).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result, rerender } = renderHook(({ open }) => useTemplateInstall(open, close, changed), {
    initialProps: { open: true },
  });
  act(() => result.current.setUrl("https://github.com/example/repo"));
  let action!: Promise<void>;
  act(() => {
    action = result.current.install();
  });
  rerender({ open: false });
  rerender({ open: true });
  act(() => result.current.setUrl("https://github.com/new/repo"));
  await act(async () => {
    finish(installed);
    await action;
  });
  expect(close).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
  expect(result.current.url).toBe("https://github.com/new/repo");
  expect(result.current.busy).toBe(false);
});

it("ZIP 入口校验文件类型并保持两种安装方式的名称", async () => {
  const { result } = renderHook(() => useTemplateInstall(true, vi.fn()));
  act(() => {
    result.current.setName("url-name");
    result.current.setMethod("file");
  });
  act(() => {
    result.current.setName("file-name");
    result.current.pickFile(new File(["x"], "bad.txt"));
  });
  expect(result.current.file).toBeNull();
  await act(async () => result.current.install());
  expect(result.current.error).toContain("选择 ZIP");
  const file = new File(["zip"], "sample.ZIP");
  act(() => result.current.pickFile(file));
  await act(async () => result.current.install());
  expect(installTemplateFromFile).toHaveBeenCalledWith(file, "file-name");
  expect(result.current.names.url).toBe("url-name");
});

it("卸载只列出后端许可项，失败保留目标并允许重试", async () => {
  const changed = vi.fn(),
    close = vi.fn();
  const { result } = renderHook(() => useTemplateRemoval(true, close, changed));
  await waitFor(() => expect(result.current.templates).toEqual([custom]));
  act(() => result.current.select(custom));
  vi.mocked(uninstallTemplate).mockRejectedValueOnce(new Error("文件正在使用"));
  await act(async () => result.current.remove());
  expect(result.current.target).toEqual(custom);
  expect(result.current.actionError).toBe("文件正在使用");
  expect(changed).not.toHaveBeenCalled();
  vi.mocked(fetchReportTemplates).mockResolvedValueOnce([]);
  await act(async () => result.current.remove());
  expect(changed).toHaveBeenCalledWith("sample");
  expect(result.current.target).toBeNull();
  expect(result.current.templates).toEqual([]);
});

it("卸载期间不能重复提交、关闭或切换确认目标", async () => {
  const close = vi.fn();
  let finish!: (value: { name: string; removed: boolean }) => void;
  vi.mocked(uninstallTemplate).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = renderHook(() => useTemplateRemoval(true, close));
  await waitFor(() => expect(result.current.templates).toHaveLength(1));
  act(() => result.current.select(custom));
  let action!: Promise<void>;
  act(() => {
    action = result.current.remove();
    void result.current.remove();
    result.current.close();
    result.current.select(null);
  });
  expect(uninstallTemplate).toHaveBeenCalledTimes(1);
  expect(close).not.toHaveBeenCalled();
  expect(result.current.target).toEqual(custom);
  await act(async () => {
    finish({ name: "sample", removed: true });
    await action;
  });
});

it("列表失败保留已读结果，关闭后迟到的卸载不影响新窗口", async () => {
  const changed = vi.fn();
  let finish!: (value: { name: string; removed: boolean }) => void;
  const { result, rerender } = renderHook(
    ({ open }) => useTemplateRemoval(open, vi.fn(), changed),
    { initialProps: { open: true } },
  );
  await waitFor(() => expect(result.current.templates).toHaveLength(1));
  vi.mocked(fetchReportTemplates).mockRejectedValueOnce(new Error("网络失败"));
  await act(async () => result.current.refresh());
  expect(result.current.templates).toEqual([custom]);
  expect(result.current.error).toBe("网络失败");
  vi.mocked(uninstallTemplate).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  act(() => result.current.select(custom));
  let action!: Promise<void>;
  act(() => {
    action = result.current.remove();
  });
  rerender({ open: false });
  rerender({ open: true });
  await waitFor(() => expect(result.current.templates).toHaveLength(1));
  await act(async () => {
    finish({ name: "sample", removed: true });
    await action;
  });
  expect(changed).not.toHaveBeenCalled();
  expect(result.current.templates).toEqual([custom]);
});
