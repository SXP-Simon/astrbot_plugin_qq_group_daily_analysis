import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LoadingState } from "@/shared/ui/loading-state";

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

it("慢加载提示不会结束加载，重新挂载重置等待并清理计时器", async () => {
  vi.useFakeTimers();
  try {
    const view = render(
      <LoadingState key="first" slowAfterMs={30000}>
        正在读取…
      </LoadingState>,
    );
    await act(async () => vi.advanceTimersByTimeAsync(29999));
    expect(screen.getByRole("status")).toHaveTextContent("正在读取…");
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(screen.getByRole("status")).toHaveTextContent("加载时间较长，仍在等待结果");
    expect(screen.getByRole("status").querySelector('[data-slot="loading-spinner"]')).toBeVisible();
    view.rerender(
      <LoadingState key="second" slowAfterMs={30000}>
        正在读取第二份…
      </LoadingState>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("正在读取第二份…");
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => vi.advanceTimersByTimeAsync(30000));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});
