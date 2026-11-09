import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchReportContent } from "@/entities/report/api/reportApi";
import { fetchTraceDetail, resumeTraceTask } from "@/entities/trace/api/traceApi";
import type { TraceRecord } from "@/entities/trace/model/types";
import type { ReportItem } from "@/entities/report/model/types";
import { useTraceActions } from "@/widgets/trace-drawer/model/useTraceActions";
import { useTraceDrawerViewModel } from "@/widgets/trace-drawer/model/useTraceDrawerViewModel";

vi.mock("@/entities/report/api/reportApi", () => ({ fetchReportContent: vi.fn() }));
vi.mock("@/entities/trace/api/traceApi", () => ({
  resumeTraceTask: vi.fn(),
  fetchTraceDetail: vi.fn(),
}));
vi.mock("@/entities/log/api/logApi", () => ({
  fetchTraceLogs: vi.fn().mockResolvedValue([]),
}));

const trace: TraceRecord = {
  trace_id: "example",
  group_id: "example-group",
  group_name: "示例群",
  platform: "satori",
  trigger_type: "manual",
  started_at: 1,
  status: "failed",
};
const report: ReportItem = {
  filename: "example.png",
  size_bytes: 10,
  modified_at: 1,
  data_url: "data:image/png;base64,example",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.mocked(fetchReportContent).mockResolvedValue(report);
  vi.mocked(fetchTraceDetail).mockResolvedValue(trace);
  vi.mocked(resumeTraceTask).mockResolvedValue({ trace_id: "resumed", message: "已提交" });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

it("切换预览与关闭后，迟到的文件内容不能覆盖当前预览", async () => {
  const first = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(first.promise);
  const view = renderHook(() => useTraceActions("example", true, trace, vi.fn()));
  act(() => {
    void view.result.current.previewFile("old.png", false);
  });
  await act(async () => view.result.current.previewFile(report.filename, false));
  await act(async () => first.resolve({ ...report, filename: "old.png" }));
  expect(view.result.current.previewReport?.filename).toBe(report.filename);
  const later = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(later.promise);
  act(() => {
    void view.result.current.previewFile("later.png", false);
  });
  act(() => view.result.current.closePreview());
  await act(async () => later.resolve(report));
  expect(view.result.current.previewOpen).toBe(false);
  expect(view.result.current.previewReport).toBeNull();
  expect(view.result.current.previewLoading).toBe(false);
  view.unmount();
});

it("预览不存在与加载异常有明确提示", async () => {
  vi.mocked(fetchReportContent)
    .mockResolvedValueOnce(null)
    .mockRejectedValueOnce(new Error("网络故障"));
  const view = renderHook(() => useTraceActions("example", true, trace, vi.fn()));
  await act(async () => view.result.current.previewFile("missing.png", false));
  expect(view.result.current.previewError).toContain("没有找到");
  await act(async () => view.result.current.previewFile("error.png", false));
  expect(view.result.current.previewError).toContain("暂时无法加载");
  view.unmount();
});

it("下载不重复请求，关闭详情后迟到的文件不会启动下载", async () => {
  const pending = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(pending.promise);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const view = renderHook(({ open }) => useTraceActions("example", open, trace, vi.fn()), {
    initialProps: { open: true },
  });
  act(() => {
    void view.result.current.downloadFile("example.png", false);
    void view.result.current.downloadFile("example.png", false);
  });
  expect(fetchReportContent).toHaveBeenCalledTimes(1);
  view.rerender({ open: false });
  await act(async () => pending.resolve(report));
  expect(click).not.toHaveBeenCalled();
  expect(view.result.current.downloading).toBe(false);
  view.unmount();
});

it("图片按文件名下载，缺少下载内容时不假报成功", async () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    expect(this.download).toBe("example.png");
    expect(this.href).toBe(report.data_url);
  });
  const view = renderHook(() => useTraceActions("example", true, trace, vi.fn()));
  await act(async () => view.result.current.downloadFile(report.filename, false));
  expect(click).toHaveBeenCalledTimes(1);
  vi.mocked(fetchReportContent).mockResolvedValueOnce({ ...report, data_url: null });
  await act(async () => view.result.current.downloadFile(report.filename, false));
  expect(view.result.current.actionError).toContain("没有可下载");
  expect(view.result.current.downloading).toBe(false);
  view.unmount();
});

it("续跑避免重复提交，失败保留弹窗，成功后跟踪回执中的新任务", async () => {
  const pending = deferred<Awaited<ReturnType<typeof resumeTraceTask>>>();
  vi.mocked(resumeTraceTask).mockReturnValueOnce(pending.promise);
  const view = renderHook(() => useTraceDrawerViewModel("example", true));
  await act(async () => {});
  act(() => {
    view.result.current.setResumeModalOpen(true);
    void view.result.current.confirmResume("provider", "template");
    void view.result.current.confirmResume("provider", "template");
  });
  expect(resumeTraceTask).toHaveBeenCalledTimes(1);
  vi.mocked(fetchTraceDetail).mockResolvedValue({
    ...trace,
    trace_id: "resumed",
    status: "succeeded",
  });
  await act(async () => pending.resolve({ trace_id: "resumed", message: "已提交" }));
  expect(fetchTraceDetail).toHaveBeenLastCalledWith("resumed", false);
  expect(view.result.current.trace?.trace_id).toBe("resumed");
  expect(view.result.current.resumeModalOpen).toBe(false);
  vi.mocked(resumeTraceTask).mockRejectedValueOnce(new Error("没有可恢复快照"));
  act(() => view.result.current.setResumeModalOpen(true));
  await act(async () => view.result.current.confirmResume());
  expect(view.result.current.resumeModalOpen).toBe(true);
  expect(view.result.current.actionError).toContain("没有可恢复快照");
  expect(view.result.current.resuming).toBe(false);
  view.unmount();
});

it("切换任务后旧续跑回执不能改变当前任务", async () => {
  const pending = deferred<Awaited<ReturnType<typeof resumeTraceTask>>>();
  vi.mocked(resumeTraceTask).mockReturnValueOnce(pending.promise);
  const view = renderHook(({ id }) => useTraceDrawerViewModel(id, true), {
    initialProps: { id: "example" },
  });
  await act(async () => {});
  act(() => {
    void view.result.current.confirmResume();
  });
  vi.mocked(fetchTraceDetail).mockResolvedValue({ ...trace, trace_id: "next" });
  await act(async () => view.rerender({ id: "next" }));
  await act(async () => pending.resolve({ trace_id: "resumed", message: "已提交" }));
  expect(view.result.current.trace?.trace_id).toBe("next");
  expect(fetchTraceDetail).not.toHaveBeenCalledWith("resumed", false);
  view.unmount();
});
