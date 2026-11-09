import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchConfigBackup, fetchConfigBackups } from "@/entities/plugin-data/api/pluginDataApi";
import { mockConfigBackups } from "@/mocks/data/configBackups";
import { ConfigBackupsViewer } from "@/features/view-config-backups/ui/ConfigBackupsViewer";

vi.mock("@/entities/plugin-data/api/pluginDataApi", () => ({
  fetchConfigBackups: vi.fn(),
  fetchConfigBackup: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchConfigBackups).mockResolvedValue(mockConfigBackups.map((item) => item.backup));
  vi.mocked(fetchConfigBackup).mockResolvedValue(mockConfigBackups[0]);
});

async function expand(label: string) {
  const summary = screen.getByText(label, { exact: true }).closest("summary");
  expect(summary).not.toBeNull();
  const details = summary!.parentElement as HTMLDetailsElement;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  await waitFor(() => expect(details.open).toBe(true));
}

it("列出旧版本和缺失元数据，按原始结构展开对象、数组和长文本", async () => {
  render(<ConfigBackupsViewer />);
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /查看备份/ }));
  });
  expect(await screen.findByText("v5.8.3")).toBeInTheDocument();
  expect(screen.getAllByText("未记录").length).toBeGreaterThanOrEqual(3);
  await act(async () => {
    fireEvent.click(screen.getAllByRole("button", { name: "查看" })[0]);
  });
  await screen.findByText("原始 JSON", { exact: true });
  await expand("原始 JSON");
  await expand("config");
  await expand("removed_group");
  await expand("example_array");
  expect(screen.getByText("[2]", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("false", { exact: true })).toBeInTheDocument();
  expect(screen.getByText("null", { exact: true, selector: "code" })).toBeInTheDocument();
  expect(screen.getByText("42", { exact: true })).toBeInTheDocument();
  await expand("prompts");
  await expand("topic_analysis");
  expect(document.querySelector("pre")?.textContent).toContain("主要观点，并说明讨论的结果。\n");
  expect(screen.queryByRole("button", { name: /恢复|应用|保存配置/ })).not.toBeInTheDocument();
}, 15000);

it("分页保留每份备份元数据，损坏项无法打开，关闭后返回入口焦点", async () => {
  const items = Array.from({ length: 6 }, (_, index) => ({
    ...mockConfigBackups[0].backup,
    filename: `backup-${index}.json`,
    error: index === 5 ? "JSON 已损坏" : null,
  }));
  vi.mocked(fetchConfigBackups).mockResolvedValue(items);
  render(<ConfigBackupsViewer />);
  const opener = screen.getByRole("button", { name: /查看备份/ });
  opener.focus();
  fireEvent.click(opener);
  const list = await screen.findByRole("list", { name: "配置备份" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(5);
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(within(list).getAllByRole("listitem")).toHaveLength(1);
  expect(within(list).getByText("backup-5.json")).toBeVisible();
  expect(within(list).getByText("无法读取：JSON 已损坏")).toBeVisible();
  expect(within(list).getByRole("button", { name: "查看" })).toBeDisabled();
  expect(fetchConfigBackup).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "关闭备份" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(opener).toHaveFocus();
});

it("列表失败可以刷新，备份被删除时给出读取失败说明", async () => {
  vi.mocked(fetchConfigBackups).mockRejectedValueOnce(new Error("offline"));
  render(<ConfigBackupsViewer />);
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /查看备份/ }));
  });
  expect(await screen.findByText(/备份列表暂时读不到/)).toBeInTheDocument();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /刷新列表/ }));
  });
  expect(fetchConfigBackups).toHaveBeenCalledTimes(2);
  expect(screen.getByText("v5.8.3")).toBeInTheDocument();
  vi.mocked(fetchConfigBackup).mockRejectedValueOnce(new Error("removed"));
  await act(async () => {
    fireEvent.click(screen.getAllByRole("button", { name: "查看" })[0]);
  });
  expect(await screen.findByText(/这份备份暂时无法打开/)).toBeInTheDocument();
  expect(fetchConfigBackup).toHaveBeenCalledWith(mockConfigBackups[0].backup.filename);
}, 15000);
