import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ExternalLink } from "@/shared/ui/ExternalLink";
import { copyToClipboard } from "@/shared/lib/clipboard";

vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
afterEach(() => vi.resetAllMocks());

it("外部地址可键盘选择和复制，关闭后回到原入口，不依赖新标签页权限", async () => {
  vi.mocked(copyToClipboard).mockResolvedValue(true);
  render(<ExternalLink href="https://example.test/font">查看字体上游</ExternalLink>);
  const trigger = screen.getByRole("button", { name: "查看字体上游" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "查看字体上游" });
  const address = within(dialog).getByRole("textbox", { name: "外部地址" });
  expect(address).toHaveValue("https://example.test/font");
  await waitFor(() => expect(address).toHaveFocus());
  expect(address).toHaveProperty("selectionEnd", "https://example.test/font".length);
  fireEvent.click(within(dialog).getByRole("button", { name: "复制地址" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("地址已复制"));
  expect(copyToClipboard).toHaveBeenCalledWith("https://example.test/font");
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭" }));
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("复制失败保留地址并提示手动复制", async () => {
  vi.mocked(copyToClipboard).mockResolvedValue(false);
  render(<ExternalLink href="https://example.test/license">字体许可</ExternalLink>);
  fireEvent.click(screen.getByRole("button", { name: "字体许可" }));
  fireEvent.click(screen.getByRole("button", { name: "复制地址" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("手动复制"));
  expect(screen.getByRole("textbox", { name: "外部地址" })).toHaveValue(
    "https://example.test/license",
  );
});

it("重复点击只复制一次，地址变化与重新打开后不接收旧复制结果", async () => {
  let resolve: (value: boolean) => void = () => {};
  vi.mocked(copyToClipboard).mockReturnValue(
    new Promise<boolean>((done) => {
      resolve = done;
    }),
  );
  const view = render(<ExternalLink href="https://example.test/old">查看上游</ExternalLink>);
  const trigger = screen.getByRole("button", { name: "查看上游" });
  fireEvent.click(trigger);
  const copy = screen.getByRole("button", { name: "复制地址" });
  act(() => {
    fireEvent.click(copy);
    fireEvent.click(copy);
  });
  expect(copyToClipboard).toHaveBeenCalledTimes(1);
  view.rerender(<ExternalLink href="https://example.test/new">查看上游</ExternalLink>);
  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  fireEvent.click(trigger);
  await act(async () => resolve(true));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "外部地址" })).toHaveValue("https://example.test/new");
  expect(screen.getByRole("button", { name: "复制地址" })).toBeEnabled();
});
