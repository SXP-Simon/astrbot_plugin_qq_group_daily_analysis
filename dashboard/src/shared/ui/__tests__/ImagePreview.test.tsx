import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ImagePreview } from "../image-preview";

afterEach(() => vi.restoreAllMocks());

it("图片加载后支持缩放、旋转、镜像与适应窗口，切换地址清除旧状态", () => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  const close = vi.fn();
  const view = render(<ImagePreview src="first.webp" title="报告示例" onClose={close} />);
  expect(screen.getByRole("button", { name: "放大" })).toBeDisabled();
  const image = screen.getByRole("img", { hidden: true });
  Object.defineProperties(image, { naturalWidth: { value: 1000 }, naturalHeight: { value: 2000 } });
  fireEvent.load(image);
  expect(image.style.width).toBe("284px");
  expect(image.style.height).toBe("568px");
  expect(screen.getByRole("button", { name: "放大" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "放大" }));
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("43%");
  expect(parseFloat(image.style.width)).toBeCloseTo(426);
  fireEvent.click(screen.getByRole("button", { name: "原始尺寸" }));
  expect(parseFloat(image.style.width)).toBeCloseTo(1000);
  fireEvent.click(screen.getByRole("button", { name: "旋转" }));
  fireEvent.click(screen.getByRole("button", { name: "镜像" }));
  expect(image.style.transform).toContain("rotate(90deg) scaleX(-1)");
  fireEvent.click(screen.getByRole("button", { name: "适应窗口" }));
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("28%");
  expect(screen.getByRole("button", { name: "镜像" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(screen.getByRole("button", { name: "放大" }));
  view.rerender(<ImagePreview src="second.webp" title="另一个示例" onClose={close} />);
  expect(screen.getByLabelText("缩放比例")).toHaveTextContent("—");
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

it("滚轮围绕指针缩放，单指拖动、双指缩放与键盘操作可用，取消手势停止拖动", () => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  render(<ImagePreview src="gesture.png" title="手势示例" onClose={vi.fn()} />);
  const image = screen.getByRole("img", { hidden: true });
  Object.defineProperties(image, { naturalWidth: { value: 1000 }, naturalHeight: { value: 2000 } });
  fireEvent.load(image);
  const area = screen.getByRole("region", { name: "图片查看区域" });
  Object.defineProperty(area, "setPointerCapture", { value: vi.fn() });
  const initial = parseFloat(image.style.width);
  const wheel = new WheelEvent("wheel", { deltaY: -100, cancelable: true, bubbles: true });
  fireEvent(area, wheel);
  expect(wheel.defaultPrevented).toBe(true);
  expect(parseFloat(image.style.width)).toBeGreaterThan(initial);
  fireEvent.keyDown(area, { key: "0" });
  expect(parseFloat(image.style.width)).toBeCloseTo(initial);
  fireEvent.keyDown(area, { key: "+" });
  expect(parseFloat(image.style.width)).toBeCloseTo(initial * 1.5);
  fireEvent.click(screen.getByRole("button", { name: "原始尺寸" }));
  // JSDOM 没有原生 PointerEvent，补充真实指针事件的必要字段。
  const pointer = (type: string, id: number, x: number, y: number) => {
    const event = new MouseEvent(type, { bubbles: true, button: 0, clientX: x, clientY: y });
    Object.defineProperty(event, "pointerId", { value: id });
    fireEvent(area, event);
  };
  area.scrollLeft = 100;
  area.scrollTop = 100;
  pointer("pointerdown", 1, 100, 100);
  pointer("pointermove", 1, 80, 60);
  expect(area.scrollLeft).toBe(120);
  expect(area.scrollTop).toBe(140);
  pointer("pointerdown", 2, 180, 60);
  const beforePinch = parseFloat(image.style.width);
  pointer("pointermove", 2, 280, 60);
  expect(parseFloat(image.style.width)).toBeGreaterThan(beforePinch);
  pointer("pointercancel", 1, 80, 60);
  pointer("pointercancel", 2, 280, 60);
  const stopped = area.scrollTop;
  pointer("pointermove", 2, 280, 10);
  expect(area.scrollTop).toBe(stopped);
  expect(image).toHaveAttribute("draggable", "false");
});

it("报告长图按宽度展开保留可读文字，通过纵向拖动浏览，不压缩为整张缩略图", () => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  render(<ImagePreview src="long.png" title="长报告" fitMode="width" onClose={vi.fn()} />);
  const image = screen.getByRole("img", { hidden: true });
  Object.defineProperties(image, {
    naturalWidth: { value: 1000 },
    naturalHeight: { value: 20000 },
  });
  fireEvent.load(image);
  expect(image.style.width).toBe("768px");
  expect(image.style.height).toBe("15360px");
  expect(screen.getByRole("button", { name: "适应宽度" })).toBeEnabled();
});
