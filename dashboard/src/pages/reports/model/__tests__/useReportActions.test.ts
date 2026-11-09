import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { fetchReportContent } from "@/entities/report/api/reportApi";
import type { ReportItem } from "@/entities/report/model/types";
import { useReportActions } from "@/pages/reports/model/useReportActions";

vi.mock("@/entities/report/api/reportApi", () => ({ fetchReportContent: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
const image: ReportItem = {
  filename: "example-a.png",
  size_bytes: 100,
  modified_at: 100,
  group_id: "123",
  trace_id: "trace-a",
};
const html: ReportItem = {
  ...image,
  filename: "example-b.html",
  trace_id: "trace-b",
  is_html: true,
};
const imageContent = { ...image, data_url: "data:image/png;base64,example" };
const htmlContent = { ...html, html_content: "<!doctype html><h1>示例报告</h1>" };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
let clicks: { filename: string; href: string }[] = [];
beforeEach(() => {
  vi.useFakeTimers();
  clicks = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicks.push({ filename: this.download, href: this.href });
  });
  URL.createObjectURL = vi.fn().mockReturnValue("blob:example-report");
  URL.revokeObjectURL = vi.fn();
  vi.mocked(fetchReportContent).mockImplementation(async (filename) =>
    filename === image.filename ? imageContent : htmlContent,
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

it("快速预览另一份报告时旧内容与错误均不能覆盖，关闭后不重开弹窗", async () => {
  const late = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(late.promise);
  const { result } = renderHook(useReportActions);
  act(() => {
    void result.current.openPreview(image);
  });
  expect(result.current.previewLoading).toBe(true);
  await act(async () => result.current.openPreview(html));
  await act(async () => late.resolve(imageContent));
  expect(result.current.selectedReport).toEqual(htmlContent);
  const failing = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(failing.promise);
  act(() => {
    void result.current.openPreview(image);
  });
  await act(async () => result.current.openPreview(html));
  await act(async () => failing.reject(new Error("旧图片失败")));
  expect(result.current.previewError).toBe("");
  const closing = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(closing.promise);
  act(() => {
    void result.current.openPreview(image);
  });
  act(() => result.current.closePreview());
  await act(async () => closing.resolve(imageContent));
  expect(result.current.previewOpen).toBe(false);
  expect(result.current.selectedReport).toBeNull();
  expect(result.current.previewLoading).toBe(false);
});

it("失败、缺少内容与错文件名均留在当前预览内，重新打开可恢复", async () => {
  const { result } = renderHook(useReportActions);
  vi.mocked(fetchReportContent).mockRejectedValueOnce(new Error("文件不可读"));
  await act(async () => result.current.openPreview(image));
  expect(result.current.previewError).toBe("文件不可读");
  expect(result.current.selectedReport?.filename).toBe(image.filename);
  vi.mocked(fetchReportContent).mockResolvedValueOnce(null);
  await act(async () => result.current.openPreview(image));
  expect(result.current.previewError).toContain("未找到报告内容");
  vi.mocked(fetchReportContent).mockResolvedValueOnce(htmlContent);
  await act(async () => result.current.openPreview(image));
  expect(result.current.previewError).toContain("文件名不一致");
  expect(result.current.selectedReport?.html_content).toBeUndefined();
  await act(async () => result.current.openPreview(image));
  expect(result.current.previewError).toBe("");
  expect(result.current.selectedReport).toEqual(imageContent);
});

it("同文件并发下载只请求一次，不同文件独立，HTML临时地址延后释放", async () => {
  const late = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(late.promise);
  const { result } = renderHook(useReportActions);
  act(() => {
    void result.current.downloadReport(image);
    void result.current.downloadReport(image);
  });
  expect(fetchReportContent).toHaveBeenCalledTimes(1);
  expect(result.current.downloadingFiles.has(image.filename)).toBe(true);
  await act(async () => result.current.downloadReport(html));
  expect(clicks).toEqual([{ filename: html.filename, href: "blob:example-report" }]);
  expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
  const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0];
  expect(blob).toHaveProperty("type", "text/html;charset=utf-8");
  expect(URL.revokeObjectURL).not.toHaveBeenCalled();
  await act(async () => late.resolve(imageContent));
  expect(clicks[1]).toEqual({ filename: image.filename, href: imageContent.data_url });
  expect(result.current.downloadingFiles.size).toBe(0);
  expect(toast.success).toHaveBeenCalledTimes(2);
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:example-report");
  expect(document.querySelector("a[download]")).toBeNull();
});

it("预览已有内容直接下载，HTML扩展名也能识别，失败可重试且不提示成功", async () => {
  const { result } = renderHook(useReportActions);
  await act(async () => result.current.downloadReport({ ...htmlContent, is_html: false }));
  expect(fetchReportContent).not.toHaveBeenCalled();
  expect(clicks[0].href).toBe("blob:example-report");
  vi.mocked(toast.success).mockClear();
  vi.mocked(fetchReportContent).mockResolvedValueOnce(null);
  await act(async () => result.current.downloadReport(image));
  expect(result.current.downloadError).toContain("未找到报告内容");
  expect(result.current.downloadingFiles.size).toBe(0);
  expect(toast.success).not.toHaveBeenCalled();
  await act(async () => result.current.downloadReport(image));
  expect(result.current.downloadError).toBe("");
  expect(clicks).toHaveLength(2);
});

it("卸载废弃在途预览和下载，同时释放未到期的临时地址", async () => {
  const { result, unmount } = renderHook(useReportActions);
  await act(async () => result.current.downloadReport(htmlContent));
  const preview = deferred<ReportItem | null>();
  const download = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent)
    .mockReturnValueOnce(preview.promise)
    .mockReturnValueOnce(download.promise);
  act(() => {
    void result.current.openPreview(image);
    void result.current.downloadReport(image);
  });
  unmount();
  await act(async () => {
    preview.resolve(imageContent);
    download.resolve(imageContent);
  });
  expect(clicks).toHaveLength(1);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:example-report");
  expect(vi.getTimerCount()).toBe(0);
});

it("弹窗下载失败在对应报告内提示，不把另一份文件的失败带入", async () => {
  const { result } = renderHook(useReportActions);
  await act(async () => result.current.openPreview(image));
  vi.mocked(fetchReportContent).mockRejectedValueOnce(new Error("读取失败"));
  await act(async () => result.current.downloadReport(image));
  expect(result.current.previewError).toContain("读取失败");
  await act(async () => result.current.openPreview(html));
  expect(result.current.previewError).toBe("");
});

it("超过三十秒仍接受当前预览，关闭后同文件重开也不接收上一轮迟到结果", async () => {
  const late = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent).mockReturnValueOnce(late.promise);
  const { result } = renderHook(useReportActions);
  act(() => {
    void result.current.openPreview(image);
  });
  await act(async () => vi.advanceTimersByTimeAsync(45000));
  expect(result.current.previewLoading).toBe(true);
  expect(result.current.previewError).toBe("");
  await act(async () => late.resolve(imageContent));
  expect(result.current.selectedReport).toEqual(imageContent);
  expect(result.current.previewLoading).toBe(false);

  const old = deferred<ReportItem | null>();
  const current = deferred<ReportItem | null>();
  vi.mocked(fetchReportContent)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  act(() => {
    void result.current.openPreview(image);
  });
  await act(async () => vi.advanceTimersByTimeAsync(30001));
  act(() => result.current.closePreview());
  act(() => {
    void result.current.openPreview(image);
  });
  await act(async () => old.resolve({ ...imageContent, data_url: "data:image/png;base64,old" }));
  expect(result.current.selectedReport).toEqual(image);
  expect(result.current.previewLoading).toBe(true);
  await act(async () => current.resolve(imageContent));
  expect(result.current.selectedReport).toEqual(imageContent);
  expect(result.current.previewOpen).toBe(true);
});
