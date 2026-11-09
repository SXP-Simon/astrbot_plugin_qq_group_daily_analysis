import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { TemplatePackages } from "@/features/install-template/ui/TemplatePackages";
import { fetchReportTemplates, uninstallTemplate } from "@/entities/report/api/reportApi";
import { copyToClipboard } from "@/shared/lib/clipboard";
vi.mock("@/entities/report/api/reportApi", () => ({
  fetchReportTemplates: vi.fn(),
  uninstallTemplate: vi.fn(),
}));
vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
const groups = [
  { directory: "demo", count: 4, size_bytes: 200 },
  { directory: "other", count: 1, size_bytes: 20 },
  { directory: ".", count: 2, size_bytes: 10 },
];
const props = {
  groups,
  directory: "demo",
  loading: false,
  busy: false,
  onSelect: vi.fn(),
  onCreate: vi.fn(),
  onInstall: vi.fn(),
  onRefresh: vi.fn(),
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchReportTemplates).mockResolvedValue([
    { id: "demo", label: "手动示例", has_typst: true, is_custom: true, can_uninstall: false },
  ]);
  vi.mocked(copyToClipboard).mockResolvedValue(true);
});
it("手动模板可整组移除，失败保留确认目标与原因，取消恢复入口焦点", async () => {
  render(<TemplatePackages {...props} />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /^选择自定义模板：手动示例/ })).toBeEnabled(),
  );
  const trigger = screen.getByRole("button", { name: "移除模板" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent("包括当前筛选未显示的文件");
  vi.mocked(uninstallTemplate).mockRejectedValueOnce(new Error("目录暂时无法写入"));
  fireEvent.click(within(dialog).getByRole("button", { name: "移除整个模板" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("目录暂时无法写入");
  expect(props.onSelect).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole("button", { name: "取消" }));
  await waitFor(() => expect(trigger).toHaveFocus());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("确认目标固定，忙碌期间不能重复移除或关闭，外部切换后不清空新目录", async () => {
  const view = render(<TemplatePackages {...props} />);
  await waitFor(() => expect(screen.queryByText("正在读取模板信息…")).not.toBeInTheDocument());
  let finish!: (value: { name: string; removed: boolean }) => void;
  vi.mocked(uninstallTemplate).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "移除模板" }));
  fireEvent.click(screen.getByRole("button", { name: "移除整个模板" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "正在移除…" })).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭" }));
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(dialog).toBeVisible();
  expect(uninstallTemplate).toHaveBeenCalledTimes(1);
  view.rerender(<TemplatePackages {...props} directory="other" />);
  expect(dialog).toHaveTextContent("demo");
  finish({ name: "demo", removed: true });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(props.onRefresh).toHaveBeenCalledOnce();
  expect(props.onSelect).not.toHaveBeenCalled();
});
it("根目录零散文件不允许整组移除，目录复制与创建安装入口保留", async () => {
  const view = render(<TemplatePackages {...props} directory="." />);
  await waitFor(() => expect(screen.queryByText("正在读取模板信息…")).not.toBeInTheDocument());
  expect(screen.getByText(/不移除整个模板存储根目录/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "移除模板" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "复制模板目录" }));
  expect(await screen.findByText("目录已复制")).toBeVisible();
  view.rerender(<TemplatePackages {...props} directory="" />);
  fireEvent.click(screen.getByRole("button", { name: "新建模板源码" }));
  fireEvent.click(screen.getByRole("button", { name: "安装模板包" }));
  expect(props.onCreate).toHaveBeenCalledOnce();
  expect(props.onInstall).toHaveBeenCalledOnce();
});
