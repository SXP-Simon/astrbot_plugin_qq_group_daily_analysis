import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { FileContentDialog } from "../FileContentDialog";
import { useManagedFiles } from "../../model/useManagedFiles";
import {
  fetchManagedContent,
  fetchManagedFiles,
  fetchManagedPartitions,
  mutateManagedFile,
  type ManagedFileContent,
} from "../../../../entities/plugin-data/api/managedFilesApi";

vi.mock("../../../../entities/plugin-data/api/managedFilesApi", () => ({
  fetchManagedPartitions: vi.fn(),
  fetchManagedFiles: vi.fn(),
  fetchManagedContent: vi.fn(),
  mutateManagedFile: vi.fn(),
  deleteManagedFiles: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const partition = {
  key: "custom_templates",
  name: "模板",
  directory: "demo",
  description: "",
  impact: "影响后续渲染",
  writable: true,
  deletable: true,
  count: 1,
  size_bytes: 5,
};
const content: ManagedFileContent = {
  name: "demo/report.html",
  text: "<h1>Demo</h1>",
  content_base64: btoa("<h1>Demo</h1>"),
  revision: "v1",
  media_type: "text/html",
};
function Harness() {
  const vm = useManagedFiles();
  return (
    <>
      <button onClick={() => vm.select(partition)}>选择分区</button>
      <button onClick={() => void vm.inspect(content.name)}>读取文件</button>
      <FileContentDialog vm={vm} editor={vm.editor} setEditor={vm.setEditor} />
    </>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchManagedPartitions).mockResolvedValue([partition]);
  vi.mocked(fetchManagedFiles).mockResolvedValue({
    items: [
      {
        name: content.name,
        revision: "v1",
        size_bytes: 5,
        modified_at: 1,
        media_type: content.media_type,
        editable: true,
        downloadable: true,
      },
    ],
    total: 1,
  });
  vi.mocked(fetchManagedContent).mockResolvedValue({ ...content });
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = vi.fn(() => "blob:file");
      static revokeObjectURL = vi.fn();
    },
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("HTML 预览保持沙盒，源码可复制且不参与执行，关闭时释放预览", async () => {
  render(<Harness />);
  fireEvent.click(screen.getByText("选择分区"));
  fireEvent.click(screen.getByText("读取文件"));
  const dialog = await screen.findByRole("dialog", { name: content.name });
  expect(within(dialog).getByTitle("报告预览")).toHaveAttribute("sandbox", "");
  expect(within(dialog).getByTitle("报告预览")).toHaveAttribute("srcdoc", content.text);
  fireEvent.mouseDown(within(dialog).getByRole("tab", { name: "HTML 源码" }), {
    button: 0,
    ctrlKey: false,
  });
  expect(within(dialog).getByRole("textbox", { name: "HTML 源码" })).toHaveValue(content.text);
  expect(within(dialog).getByRole("textbox", { name: "HTML 源码" })).toHaveAttribute("readonly");
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭文件" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:file");
});

it("保存冲突在编辑窗口提示并保留输入和修订号，取消返回文件", async () => {
  vi.mocked(mutateManagedFile).mockRejectedValue(new Error("文件已被更新，请重新读取"));
  render(<Harness />);
  fireEvent.click(screen.getByText("选择分区"));
  fireEvent.click(screen.getByText("读取文件"));
  fireEvent.click(await screen.findByRole("button", { name: "编辑源码" }));
  const editor = await screen.findByRole("dialog", { name: "替换或编辑文件" });
  fireEvent.change(within(editor).getByRole("textbox", { name: "文件内容" }), {
    target: { value: "新的中文正文" },
  });
  fireEvent.click(within(editor).getByRole("button", { name: "保存" }));
  expect(await within(editor).findByRole("alert")).toHaveTextContent("文件已被更新");
  expect(within(editor).getByRole("textbox", { name: "文件内容" })).toHaveValue("新的中文正文");
  expect(mutateManagedFile).toHaveBeenCalledWith(
    expect.objectContaining({ name: content.name, revision: "v1", operation: "replace" }),
  );
  fireEvent.click(within(editor).getByRole("button", { name: "取消" }));
  expect(await screen.findByRole("dialog", { name: content.name })).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("删除须确认当前文件，失败保留目标与失败原因", async () => {
  vi.mocked(mutateManagedFile).mockRejectedValue(new Error("文件正在使用"));
  render(<Harness />);
  fireEvent.click(screen.getByText("选择分区"));
  fireEvent.click(screen.getByText("读取文件"));
  fireEvent.click(await screen.findByRole("button", { name: "删除文件" }));
  expect(mutateManagedFile).not.toHaveBeenCalled();
  const confirm = screen.getByRole("region", { name: "删除文件确认" });
  expect(confirm).toHaveTextContent(content.name);
  fireEvent.click(within(confirm).getByRole("button", { name: "确认删除" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("文件正在使用");
  expect(confirm).toBeVisible();
  expect(mutateManagedFile).toHaveBeenCalledWith({
    partition: "custom_templates",
    operation: "delete",
    name: content.name,
    revision: "v1",
  });
});

it("损坏内容给出重新读取入口，不生成可下载的错误文件", async () => {
  vi.mocked(fetchManagedContent).mockResolvedValueOnce({ ...content, content_base64: "!!!" });
  render(<Harness />);
  fireEvent.click(screen.getByText("选择分区"));
  fireEvent.click(screen.getByText("读取文件"));
  expect(await screen.findByRole("alert")).toHaveTextContent("文件内容无法解码");
  expect(screen.getByRole("button", { name: "下载原文件" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(screen.getByRole("button", { name: "下载原文件" })).toBeEnabled();
});

it("文件图片放大后使用相同的缩放手势查看器，Escape 只关闭放大窗口", async () => {
  vi.mocked(fetchManagedContent).mockResolvedValue({
    ...content,
    media_type: "image/png",
    text: null,
    content_base64: "aW1hZ2U=",
  });
  render(<Harness />);
  fireEvent.click(screen.getByText("选择分区"));
  fireEvent.click(screen.getByText("读取文件"));
  fireEvent.click(await screen.findByRole("button", { name: "放大图片" }));
  const area = screen.getByRole("region", { name: "图片查看区域" });
  expect(area).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "原始尺寸" })).toBeDisabled();
  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  await waitFor(() =>
    expect(screen.queryByRole("region", { name: "图片查看区域" })).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("dialog", { name: content.name })).toBeInTheDocument();
});
