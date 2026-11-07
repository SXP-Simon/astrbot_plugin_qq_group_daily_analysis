import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StoredRecordsTab } from "../StoredRecordsTab";
import {
  fetchManagedRecords,
  fetchManagedRecord,
  mutateManagedRecord,
} from "../../../../entities/plugin-data/api/managedRecordsApi";
vi.mock("../../../../entities/plugin-data/api/managedRecordsApi", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("../../../../entities/plugin-data/api/managedRecordsApi")
  >()),
  fetchManagedRecords: vi.fn(),
  fetchManagedRecord: vi.fn(),
  mutateManagedRecord: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const one = {
  locator: { kind: "history", key: "analysis_string-id_2026-11-07", group_id: "string-id" },
  name: "analysis_string-id_2026-11-07",
  size_bytes: 0,
};
const two = {
  ...one,
  locator: { ...one.locator, key: "analysis_other_2026-11-06" },
  name: "analysis_other_2026-11-06",
  size_bytes: 120,
};
it("搜索需明确提交，清空立即生效，切换类型保留已提交条件并重置选择", async () => {
  vi.mocked(fetchManagedRecords).mockResolvedValue({ items: [one], total: 1 });
  render(<StoredRecordsTab />);
  expect(await screen.findByText(one.name)).toBeInTheDocument();
  expect(screen.getByText("0 B")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: `选择记录 ${one.name}` }));
  expect(screen.getByText(/已选 1 项/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索业务记录" }), {
    target: { value: "string-id" },
  });
  expect(fetchManagedRecords).toHaveBeenLastCalledWith("history", "", 1);
  fireEvent.click(screen.getByRole("button", { name: "搜索" }));
  await waitFor(() =>
    expect(fetchManagedRecords).toHaveBeenLastCalledWith("history", "string-id", 1),
  );
  expect(screen.getByText(/已选 0 项/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: "头像缓存" }));
  await waitFor(() =>
    expect(fetchManagedRecords).toHaveBeenLastCalledWith("avatar", "string-id", 1),
  );
  expect(screen.queryByRole("button", { name: "导入历史记录" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清空搜索" }));
  await waitFor(() => expect(fetchManagedRecords).toHaveBeenLastCalledWith("avatar", "", 1));
  expect(screen.getByRole("searchbox")).toHaveValue("");
});
it("跨页选择保留身份，批量删除读取各自修订号并保留失败项", async () => {
  vi.mocked(fetchManagedRecords).mockImplementation(async (_kind, _search, page) => ({
    items: page === 1 ? [one] : [two],
    total: 21,
  }));
  vi.mocked(fetchManagedRecord).mockImplementation(async (locator) => ({
    locator,
    revision: locator.key === one.name ? "v1" : "v2",
    data: {},
  }));
  vi.mocked(mutateManagedRecord)
    .mockResolvedValueOnce(undefined)
    .mockRejectedValueOnce(new Error("记录正在使用"));
  render(<StoredRecordsTab />);
  await screen.findByText(one.name);
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页记录" }));
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  await screen.findByText(two.name);
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页记录" }));
  expect(screen.getByText(/已选 2 项/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "删除所选" }));
  const confirm = screen.getByRole("dialog");
  expect(confirm).toHaveTextContent("2 项分析存档");
  expect(mutateManagedRecord).not.toHaveBeenCalled();
  fireEvent.click(within(confirm).getByRole("button", { name: "删除所选" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(mutateManagedRecord).toHaveBeenNthCalledWith(1, {
    locator: one.locator,
    revision: "v1",
    operation: "delete",
  });
  expect(mutateManagedRecord).toHaveBeenNthCalledWith(2, {
    locator: two.locator,
    revision: "v2",
    operation: "delete",
  });
  expect(screen.getByText(/已选 1 项/)).toBeInTheDocument();
  expect(screen.getByText(/记录正在使用/)).toBeInTheDocument();
});
it("限定分区保留管理和导入，列表失败不显示空数据成功状态", async () => {
  vi.mocked(fetchManagedRecords).mockRejectedValueOnce(new Error("读取失败"));
  const { rerender } = render(<StoredRecordsTab onlyKind="history" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("读取失败");
  expect(screen.queryByText("暂无记录。")).not.toBeInTheDocument();
  expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  vi.mocked(fetchManagedRecords).mockResolvedValue({ items: [one], total: 1 });
  fireEvent.click(screen.getByRole("button", { name: "刷新记录" }));
  await screen.findByText(one.name);
  vi.mocked(fetchManagedRecord).mockResolvedValue({
    locator: one.locator,
    revision: "v1",
    data: { unknown: [0, false] },
  });
  fireEvent.click(screen.getByRole("button", { name: "查看与管理" }));
  expect(await screen.findByRole("textbox", { name: "业务记录 JSON" })).toHaveValue(
    JSON.stringify({ unknown: [0, false] }, null, 2),
  );
  fireEvent.click(screen.getByRole("button", { name: "关闭记录" }));
  fireEvent.click(screen.getByRole("button", { name: "导入历史记录" }));
  expect(screen.getByRole("dialog", { name: "导入业务记录" })).toBeInTheDocument();
  await act(async () => rerender(<StoredRecordsTab onlyKind="avatar" />));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(fetchManagedRecords).toHaveBeenLastCalledWith("avatar", "", 1);
});
