import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { Toaster } from "../sonner";
const theme = vi.hoisted(() => ({ isDark: false }));
vi.mock("../../lib/useTheme", () => ({ useTheme: () => theme }));
afterEach(() => {
  toast.dismiss();
  theme.isDark = false;
});

it("通知可由键盘定位、使用中文关闭名称，并跟随宿主主题", async () => {
  const { rerender } = render(
    <>
      <button>原操作入口</button>
      <Toaster />
    </>,
  );
  act(() => {
    toast.success("分析已提交", { duration: Infinity });
  });
  const label = await screen.findByText("分析已提交");
  const notification = label.closest("li")!;
  expect(notification).toHaveStyle({ boxShadow: "none", borderRadius: "12px" });
  expect(notification.closest("ol")).toHaveAttribute("data-sonner-theme", "light");
  const origin = screen.getByRole("button", { name: "原操作入口" });
  act(() => origin.focus());
  fireEvent.keyDown(document, { altKey: true, code: "KeyT" });
  await waitFor(() => expect(notification.closest("ol")).toHaveFocus());
  expect(screen.getByRole("button", { name: "关闭提示" })).toBeVisible();
  theme.isDark = true;
  rerender(
    <>
      <button>原操作入口</button>
      <Toaster />
    </>,
  );
  expect(notification.closest("ol")).toHaveAttribute("data-sonner-theme", "dark");
  fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
  await waitFor(() => expect(screen.queryByText("分析已提交")).not.toBeInTheDocument());
});
