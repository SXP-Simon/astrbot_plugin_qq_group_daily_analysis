import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useManagedFiles } from "../../model/useManagedFiles";
import { ManagedFileList } from "../ManagedFileList";
import type {
  ManagedFile,
  ManagedPartition,
} from "../../../../entities/plugin-data/api/managedFilesApi";
import { copyToClipboard } from "../../../../shared/lib/clipboard";
import { fetchManagedPartitions } from "../../../../entities/plugin-data/api/managedFilesApi";

vi.mock("../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedPartitions: vi.fn(),
}));
vi.mock("../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
beforeEach(() => vi.mocked(fetchManagedPartitions).mockResolvedValue([]));
const partition: ManagedPartition = {
  key: "reports",
  name: "历史报告",
  directory: "reports",
  description: "",
  impact: "删除后无法预览",
  count: 21,
  size_bytes: 100,
  writable: false,
  deletable: true,
};
const file: ManagedFile = {
  name: "example.png",
  revision: "original",
  size_bytes: 1,
  modified_at: 1,
  media_type: "image/png",
  editable: false,
  downloadable: true,
};
const references = {
  loading: false,
  error: "",
  references: new Map<string, string[]>(),
  refresh: vi.fn(),
};

it("本页全选保留跨页选择，取消本页只移除当前文件", async () => {
  const { result } = renderHook(useManagedFiles);
  await act(async () => {});
  const selectFiles = vi.fn();
  const vm = {
    ...result.current,
    files: [file],
    selected: [{ ...file, name: "older.png" }],
    selectFiles,
  };
  const { rerender } = render(
    <ManagedFileList vm={vm} partition={partition} references={references} />,
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页文件（最多 200）" }));
  expect(selectFiles).toHaveBeenLastCalledWith(["older.png", "example.png"]);
  rerender(
    <ManagedFileList
      vm={{ ...vm, selected: [...vm.selected, file] }}
      partition={partition}
      references={references}
    />,
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页文件（最多 200）" }));
  expect(selectFiles).toHaveBeenLastCalledWith(["older.png"]);
});

it("首次加载在表格内占位，刷新保留已读行，不短暂显示空结果", async () => {
  const { result } = renderHook(useManagedFiles);
  await act(async () => {});
  const vm = { ...result.current, files: [], loading: true, total: 0 };
  const { rerender } = render(
    <ManagedFileList vm={vm} partition={partition} references={references} />,
  );
  expect(
    within(screen.getByRole("region", { name: "文件列表" })).getByRole("status"),
  ).toHaveTextContent("正在读取文件列表");
  rerender(
    <ManagedFileList
      vm={{ ...vm, files: [file], total: 1 }}
      partition={partition}
      references={references}
    />,
  );
  expect(screen.getByText(file.name)).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("正在刷新文件列表");
  expect(within(screen.getByRole("region", { name: "文件列表" })).queryByRole("status")).toBeNull();
});

it("确认固定所选文件，删除失败保留弹窗且 Escape 不关闭父层", async () => {
  const { result } = renderHook(useManagedFiles);
  await act(async () => {});
  const remove = vi.fn().mockResolvedValue(false);
  const vm = { ...result.current, files: [file], selected: [file], deleteSelected: remove };
  const { rerender } = render(
    <ManagedFileList vm={vm} partition={partition} references={references} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "删除所选" }));
  rerender(
    <ManagedFileList
      vm={{ ...vm, selected: [{ ...file, name: "other.png" }], actionError: "连接失败" }}
      partition={partition}
      references={references}
    />,
  );
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("example.png")).toBeVisible();
  expect(within(dialog).queryByText("other.png")).not.toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "删除所选" }));
  await waitFor(() => expect(remove).toHaveBeenCalledWith([file], "reports"));
  expect(screen.getByRole("alert")).toHaveTextContent("连接失败");
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it("搜索按提交执行，可清空，上传重复文件仍通知 ViewModel", async () => {
  const { result } = renderHook(useManagedFiles);
  await act(async () => {});
  const searchFiles = vi.fn(),
    prepareUpload = vi.fn();
  const vm = { ...result.current, searchFiles, prepareUpload };
  render(
    <ManagedFileList
      vm={vm}
      partition={{ ...partition, key: "custom_templates", writable: true }}
      references={references}
    />,
  );
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索文件" }), {
    target: { value: "  report  " },
  });
  expect(searchFiles).not.toHaveBeenCalled();
  fireEvent.submit(screen.getByRole("searchbox").closest("form")!);
  expect(searchFiles).toHaveBeenLastCalledWith("report");
  fireEvent.click(screen.getByRole("button", { name: "清空文件搜索" }));
  expect(searchFiles).toHaveBeenLastCalledWith("");
  const upload = new File(["test"], "report.typ");
  const input = screen.getByLabelText("上传分区文件");
  fireEvent.change(input, { target: { files: [upload] } });
  fireEvent.change(input, { target: { files: [upload] } });
  expect(prepareUpload).toHaveBeenCalledTimes(2);
});

it("长文件路径与配置引用保留完整内容，复制和预览仍操作同一文件", async () => {
  const name = "daily_comic/comic_characters/templates/character/reference_images/character.png";
  const reference = "daily_comic.comic_characters[0].reference_images[0]";
  const { result } = renderHook(useManagedFiles);
  await act(async () => {});
  const inspect = vi.fn();
  vi.mocked(copyToClipboard).mockResolvedValue(true);
  render(
    <ManagedFileList
      vm={{ ...result.current, files: [{ ...file, name }], inspect }}
      partition={{ ...partition, key: "config_files", name: "配置参考素材" }}
      references={{ ...references, references: new Map([[name, [reference]]]) }}
    />,
  );
  const filename = screen.getByText(name, { exact: true });
  expect(filename).toHaveAttribute("title", name);
  expect(screen.getByText(`files/${name}`, { exact: true })).toBeVisible();
  expect(screen.getByText(reference, { exact: true })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: `复制引用路径 files/${name}` }));
  await waitFor(() => expect(copyToClipboard).toHaveBeenCalledWith(`files/${name}`));
  fireEvent.click(screen.getByRole("button", { name: "预览 / 下载" }));
  expect(inspect).toHaveBeenCalledWith(name);
  expect(screen.getByRole("checkbox", { name: `选择文件 ${name}` })).toBeEnabled();
});
