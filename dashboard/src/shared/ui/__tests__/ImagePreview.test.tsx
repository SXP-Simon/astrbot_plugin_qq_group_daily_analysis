import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ImagePreview } from "../image-preview";

it("图片加载后支持缩放、旋转、镜像与适应窗口，切换地址清除旧状态", () => {
  const close = vi.fn();
  const view = render(<ImagePreview src="first.webp" title="报告示例" onClose={close} />);
  expect(screen.getByRole("button", { name: "放大" })).toBeDisabled();
  const image = screen.getByRole("img", { hidden: true });
  Object.defineProperties(image, { naturalWidth: { value: 1000 }, naturalHeight: { value: 2000 } });
  fireEvent.load(image);
  expect(screen.getByRole("button", { name: "放大" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "放大" }));
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("150%");
  fireEvent.click(screen.getByRole("button", { name: "旋转" }));
  fireEvent.click(screen.getByRole("button", { name: "镜像" }));
  expect(image.style.transform).toContain("rotate(90deg) scaleX(-1)");
  fireEvent.click(screen.getByRole("button", { name: "适应窗口" }));
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("100%");
  expect(screen.getByRole("button", { name: "镜像" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(screen.getByRole("button", { name: "放大" }));
  view.rerender(<ImagePreview src="second.webp" title="另一个示例" onClose={close} />);
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("100%");
  expect(screen.getByRole("button", { name: "放大" })).toBeDisabled();
});

it("加载失败不显示成功图片，可换图继续，图库按钮按可用方向启用", () => {
  const next = vi.fn();
  const view = render(
    <ImagePreview
      src="broken.webp"
      title="失败示例"
      onClose={vi.fn()}
      onNext={next}
      position="1 / 2"
    />,
  );
  expect(screen.getByRole("button", { name: "上一张" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "下一张" }));
  expect(next).toHaveBeenCalledOnce();
  fireEvent.error(screen.getByRole("img", { hidden: true }));
  expect(screen.getByRole("alert")).toHaveTextContent("图片未能加载");
  expect(screen.getByRole("button", { name: "放大" })).toBeDisabled();
  view.rerender(<ImagePreview src={null} title="缺失示例" onClose={vi.fn()} />);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByText("此项没有可用的预览图片。")).toBeInTheDocument();
});

it("Escape 只请求关闭当前预览", () => {
  const close = vi.fn();
  render(<ImagePreview src={null} loading title="正在读取" onClose={close} />);
  expect(screen.getByRole("status", { name: "图片加载状态" })).toHaveTextContent("正在加载");
  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  expect(close).toHaveBeenCalledOnce();
});
