import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ReportPreviewModal } from "../ReportPreviewModal";

const report = {
  filename: "report.png",
  size_bytes: 1024,
  modified_at: 1,
  data_url: "data:image/png;base64,example",
};
it("报告图片使用统一查看器，解码前显示加载，加载后提供缩放工具", () => {
  render(
    <ReportPreviewModal
      open
      loading={false}
      report={report}
      onClose={vi.fn()}
      onDownload={vi.fn()}
    />,
  );
  expect(screen.getByRole("status", { name: "图片加载状态" })).toBeInTheDocument();
  const image = screen.getByRole("img", { hidden: true });
  Object.defineProperties(image, { naturalWidth: { value: 1000 }, naturalHeight: { value: 3000 } });
  fireEvent.load(image);
  expect(screen.getByRole("button", { name: "原始尺寸" })).toBeEnabled();
  expect(screen.getByRole("region", { name: "图片查看区域" })).toHaveAttribute(
    "aria-busy",
    "false",
  );
});
it("失败后允许重新加载，关闭仍可操作，不能把无内容当作完成", () => {
  const retry = vi.fn();
  const close = vi.fn();
  render(
    <ReportPreviewModal
      open
      loading={false}
      report={null}
      error="服务连接中断"
      onClose={close}
      onRetry={retry}
      onDownload={vi.fn()}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("服务连接中断");
  fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
  expect(retry).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "关闭预览" }));
  expect(close).toHaveBeenCalledOnce();
});

it("慢传输只改变提示，切换文件重新计时，最终收到内容仍正常展示", async () => {
  vi.useFakeTimers();
  try {
    const props = { open: true, loading: true, report, onClose: vi.fn(), onDownload: vi.fn() };
    const view = render(<ReportPreviewModal {...props} />);
    await act(async () => vi.advanceTimersByTimeAsync(30000));
    expect(screen.getByRole("status")).toHaveTextContent("加载时间较长，仍在等待结果");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭预览" })).toBeEnabled();
    const next = { ...report, filename: "second.png" };
    view.rerender(<ReportPreviewModal {...props} report={next} />);
    expect(screen.getByRole("status")).toHaveTextContent("正在加载报告");
    await act(async () => vi.advanceTimersByTimeAsync(30000));
    view.rerender(<ReportPreviewModal {...props} loading={false} report={next} />);
    const image = screen.getByRole("img", { hidden: true });
    fireEvent.load(image);
    expect(screen.queryByText(/加载时间较长/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "下载图片" })).toBeEnabled();
    view.unmount();
    // Radix 卸载后的焦点恢复会排入零延迟任务。
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
