import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StorageOverview } from "@/pages/plugin-data/ui/partitions/StorageOverview";

afterEach(cleanup);
const partition = {
  key: "typst_fonts",
  name: "Typst 字体",
  directory: "data/typst/fonts",
  description: "主题共用字体",
  impact: "影响后续排版",
  writable: true,
  deletable: true,
  count: 3,
  size_bytes: 30,
};
const vm = {
  partitions: [partition],
  totals: { totalBytes: 10000, totalFiles: 3, assetBytes: 30 },
  overviewLoading: false,
  error: "",
  refresh: vi.fn(async () => {}),
};
it("分区用途、完整路径和管理能力可见，管理操作传递原分区", () => {
  const select = vi.fn();
  render(<StorageOverview vm={vm} onSelect={select} />);
  const row = screen.getByRole("row", { name: /Typst 字体/ });
  expect(row).toHaveTextContent("data/typst/fonts");
  expect(row).toHaveTextContent("补齐 / 替换 / 移除");
  expect(row).toHaveTextContent("< 1%");
  const meter = within(row).getByRole("meter", { name: "Typst 字体占总空间" });
  expect(meter).toHaveAttribute("aria-valuenow", "0.3");
  expect(meter).toHaveAttribute("aria-valuemax", "100");
  fireEvent.click(within(row).getByRole("button", { name: "管理" }));
  expect(select).toHaveBeenCalledWith(partition);
  expect(screen.getByRole("region", { name: "存储分区表格，可横向滚动" })).toHaveAttribute(
    "tabindex",
    "0",
  );
});
it("首次读取显示加载状态而不是零占用，空结果有明确提示", () => {
  const empty = { ...vm, partitions: [], totals: { totalBytes: 0, totalFiles: 0, assetBytes: 0 } };
  const view = render(
    <StorageOverview vm={{ ...empty, overviewLoading: true }} onSelect={vi.fn()} />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("正在读取存储概览");
  expect(screen.queryByText("0 B")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "刷新概览" })).toBeDisabled();
  view.rerender(<StorageOverview vm={empty} onSelect={vi.fn()} />);
  expect(screen.getByText("暂无受管理分区")).toBeVisible();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
it("刷新失败仍能查看已有分区并重试", () => {
  const refresh = vi.fn();
  render(<StorageOverview vm={{ ...vm, error: "读取失败", refresh }} onSelect={vi.fn()} />);
  expect(screen.getByRole("alert")).toHaveTextContent("读取失败");
  expect(screen.getByRole("row", { name: /Typst 字体/ })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(refresh).toHaveBeenCalledTimes(1);
});
