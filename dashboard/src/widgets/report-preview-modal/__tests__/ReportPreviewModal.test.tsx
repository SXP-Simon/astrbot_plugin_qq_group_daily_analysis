import { fireEvent, render, screen } from "@testing-library/react";
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
      error="读取超过 30 秒"
      onClose={close}
      onRetry={retry}
      onDownload={vi.fn()}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("读取超过 30 秒");
  fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
  expect(retry).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "关闭预览" }));
  expect(close).toHaveBeenCalledOnce();
});
