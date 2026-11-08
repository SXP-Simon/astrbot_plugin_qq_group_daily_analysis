import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { LoadingState } from "../loading-state";

it("加载提示有主题色图标和文本，骨架对读屏隐藏并尊重减少动态效果", () => {
  const view = render(
    <LoadingState skeleton aria-label="列表加载状态">
      正在读取记录…
    </LoadingState>,
  );
  const status = screen.getByRole("status", { name: "列表加载状态" });
  expect(status).toHaveTextContent("正在读取记录");
  const spinner = status.querySelector('[data-slot="loading-spinner"]');
  expect(spinner).toHaveAttribute("aria-hidden", "true");
  expect(spinner).toHaveClass("text-primary-ink", "animate-spin", "motion-reduce:animate-none");
  expect(status.querySelector(".motion-safe\\:animate-pulse")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
  view.rerender(<LoadingState>正在刷新记录…</LoadingState>);
  expect(screen.getByRole("status").querySelector(".motion-safe\\:animate-pulse")).toBeNull();
});
