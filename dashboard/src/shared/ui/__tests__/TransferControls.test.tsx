import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { Alert } from "@/shared/ui/alert";
import { Progress } from "@/shared/ui/progress";
import { CopyButton } from "@/shared/ui/copy-button";
import { copyToClipboard } from "@/shared/lib/clipboard";
vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
it("进度只在已知时声明数值，拒绝非有限百分比并限制边界", () => {
  const view = render(<Progress label="上传" value={0} />);
  expect(screen.getByRole("progressbar", { name: "上传" })).toHaveAttribute("aria-valuenow", "0");
  view.rerender(<Progress label="上传" value={null} />);
  expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  view.rerender(<Progress label="上传" value={Infinity} />);
  expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  view.rerender(<Progress label="上传" value={125} />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
});
it("错误提示及时宣读，普通成功与警告保留文字和语义配色", () => {
  const view = render(<Alert variant="destructive">保存失败</Alert>);
  expect(screen.getByRole("alert")).toHaveTextContent("保存失败");
  view.rerender(<Alert variant="warning">连接等待过长</Alert>);
  expect(screen.getByRole("status")).toHaveClass("text-warning");
  expect(screen.getByRole("status")).toHaveTextContent("连接等待过长");
});
it("复制锁阻止重复操作，字段变化后拒绝迟到反馈，失败提供手动复制提示", async () => {
  let finish!: (value: boolean) => void;
  vi.mocked(copyToClipboard).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const view = render(<CopyButton text="old" label="复制地址" />);
  fireEvent.click(screen.getByRole("button", { name: "复制地址" }));
  expect(screen.getByRole("button")).toBeDisabled();
  fireEvent.click(screen.getByRole("button"));
  expect(copyToClipboard).toHaveBeenCalledTimes(1);
  view.rerender(<CopyButton text="new" label="复制地址" />);
  await act(async () => {
    finish(true);
  });
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
  vi.mocked(copyToClipboard).mockResolvedValueOnce(false);
  fireEvent.click(screen.getByRole("button"));
  expect(await screen.findByText("复制失败，请手动选择文字。")).toBeVisible();
  expect(copyToClipboard).toHaveBeenLastCalledWith("new");
});
