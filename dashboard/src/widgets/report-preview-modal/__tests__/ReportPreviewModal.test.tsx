import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ReportPreviewModal } from "@/widgets/report-preview-modal/ReportPreviewModal";
import { copyToClipboard } from "@/shared/lib/clipboard";

vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
afterEach(() => vi.clearAllMocks());

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

it.each([
  { filename: "report.png", is_html: false, loading: true, error: "" },
  { filename: "report.html", is_html: true, loading: true, error: "" },
  { filename: "report.png", is_html: false, loading: false, error: "读取失败" },
])(
  "$filename 加载状态为 $loading 时已有路径可以展开和复制",
  async ({ filename, is_html, loading, error }) => {
    vi.mocked(copyToClipboard).mockResolvedValue(true);
    const absolutePath = `/reports/${filename}`;
    const view = render(
      <ReportPreviewModal
        open
        loading={loading}
        report={{
          filename,
          is_html,
          size_bytes: 1024,
          modified_at: 1,
          absolute_path: absolutePath,
        }}
        error={error}
        onClose={vi.fn()}
        onDownload={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("服务器文件位置"));
    expect(screen.getByText(absolutePath)).toBeVisible();
    const copy = screen.getByRole("button", { name: "复制路径" });
    expect(copy).toBeEnabled();
    fireEvent.click(copy);
    await screen.findByText("已复制路径");
    expect(copyToClipboard).toHaveBeenCalledWith(absolutePath);
    expect(screen.getByRole("button", { name: is_html ? "下载 HTML" : "下载图片" })).toHaveProperty(
      "disabled",
      loading,
    );
    if (error) expect(screen.getByRole("alert")).toHaveTextContent(error);
    else {
      expect(screen.getByText("正在加载报告…")).toBeVisible();
      view.rerender(
        <ReportPreviewModal
          open
          loading={false}
          report={{
            filename,
            is_html,
            size_bytes: 1024,
            modified_at: 1,
            absolute_path: absolutePath,
            ...(is_html ? { html_content: "<h1>示例报告</h1>" } : { data_url: report.data_url }),
          }}
          onClose={vi.fn()}
          onDownload={vi.fn()}
        />,
      );
      expect(screen.getByText(absolutePath)).toBeVisible();
      expect(screen.getByText("服务器文件位置").closest("details")).toHaveAttribute("open");
    }
  },
);

it("没有路径时不显示空入口，切换文件后不会展示旧路径或复制反馈", async () => {
  vi.mocked(copyToClipboard).mockResolvedValue(false);
  const props = { open: true, loading: true, onClose: vi.fn(), onDownload: vi.fn() };
  const view = render(
    <ReportPreviewModal {...props} report={{ ...report, absolute_path: "/reports/old.png" }} />,
  );
  fireEvent.click(screen.getByText("服务器文件位置"));
  fireEvent.click(screen.getByRole("button", { name: "复制路径" }));
  await screen.findByText("无法复制，请手动选择路径。");
  view.rerender(<ReportPreviewModal {...props} report={{ ...report, filename: "new.png" }} />);
  expect(screen.queryByText("服务器文件位置")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "复制路径" })).not.toBeInTheDocument();
  expect(screen.queryByText("/reports/old.png")).not.toBeInTheDocument();
  expect(screen.queryByText("无法复制，请手动选择路径。")).not.toBeInTheDocument();
  view.rerender(
    <ReportPreviewModal
      {...props}
      report={{ ...report, filename: "new.png", absolute_path: "/reports/new.png" }}
    />,
  );
  expect(screen.queryByText("无法复制，请手动选择路径。")).not.toBeInTheDocument();
});
