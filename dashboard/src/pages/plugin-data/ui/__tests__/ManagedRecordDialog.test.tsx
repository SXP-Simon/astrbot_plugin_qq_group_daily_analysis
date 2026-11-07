import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ManagedRecordDialog } from "../ManagedRecordDialog";
import {
  fetchManagedRecord,
  mutateManagedRecord,
} from "../../../../entities/plugin-data/api/managedRecordsApi";
import { copyToClipboard } from "../../../../shared/lib/clipboard";
vi.mock("../../../../entities/plugin-data/api/managedRecordsApi", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("../../../../entities/plugin-data/api/managedRecordsApi")
  >()),
  fetchManagedRecord: vi.fn(),
  mutateManagedRecord: vi.fn(),
}));
vi.mock("../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});
const locator = {
  kind: "checkpoint",
  group_id: "discord:string-id",
  date_str: "2026-11-07",
  stage_name: "LLM_ANALYSIS",
  trace_id: "trace-1",
};
const record = { locator, revision: "v1", data: { nested: { messages: ["测试", 0, false] } } };
it("保留 JSON 导出、只读与编辑，失败保存保留输入和原修订号", async () => {
  vi.mocked(fetchManagedRecord).mockResolvedValue(record);
  const close = vi.fn(),
    changed = vi.fn();
  render(<ManagedRecordDialog locator={locator} onClose={close} onChanged={changed} />);
  const textarea = await screen.findByRole("textbox", { name: "业务记录 JSON" });
  expect(textarea).toHaveAttribute("readonly");
  expect(screen.getByText(/任务归属、创建时间和有效期不可修改/)).toBeInTheDocument();
  let blob: Blob | undefined;
  const createObjectURL = vi.fn((value: Blob) => {
    blob = value;
    return "blob:record";
  });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "导出完整 JSON" }));
  expect(click).toHaveBeenCalledOnce();
  expect(blob?.type).toBe("application/json");
  fireEvent.click(screen.getByRole("button", { name: "编辑产物" }));
  expect(textarea).not.toHaveAttribute("readonly");
  fireEvent.change(textarea, { target: { value: '{"nested":{"messages":["修订"]}}' } });
  vi.mocked(mutateManagedRecord).mockRejectedValueOnce(new Error("修订冲突，请重新读取"));
  fireEvent.click(screen.getByRole("button", { name: "保存修订" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("修订冲突");
  expect(textarea).toHaveValue('{"nested":{"messages":["修订"]}}');
  expect(close).not.toHaveBeenCalled();
  expect(mutateManagedRecord).toHaveBeenCalledWith({
    locator,
    revision: "v1",
    operation: "replace",
    data: { nested: { messages: ["修订"] } },
  });
  vi.mocked(mutateManagedRecord).mockResolvedValueOnce(undefined);
  fireEvent.click(screen.getByRole("button", { name: "保存修订" }));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  expect(changed).toHaveBeenCalledOnce();
});
it("删除需要确认，失败保留目标；切换记录重置确认和编辑内容", async () => {
  vi.mocked(fetchManagedRecord).mockResolvedValue(record);
  const close = vi.fn();
  const { rerender } = render(
    <ManagedRecordDialog locator={locator} onClose={close} onChanged={vi.fn()} />,
  );
  await screen.findByRole("textbox");
  fireEvent.click(screen.getByRole("button", { name: "删除此记录" }));
  expect(screen.getByRole("region", { name: "删除确认" })).toHaveTextContent("trace-1");
  expect(mutateManagedRecord).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "取消删除" }));
  expect(screen.queryByRole("region", { name: "删除确认" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "删除此记录" }));
  vi.mocked(mutateManagedRecord).mockRejectedValueOnce(new Error("记录已更新"));
  fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("记录已更新");
  expect(close).not.toHaveBeenCalled();
  const next = { ...locator, trace_id: "trace-2" };
  vi.mocked(fetchManagedRecord).mockResolvedValue({
    ...record,
    locator: next,
    data: { second: true },
  });
  rerender(<ManagedRecordDialog locator={next} onClose={close} onChanged={vi.fn()} />);
  expect(await screen.findByRole("textbox")).toHaveValue(JSON.stringify({ second: true }, null, 2));
  expect(screen.queryByRole("region", { name: "删除确认" })).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
it("读取失败能重试，头像支持放大、返回和缓存键复制", async () => {
  const avatarLocator = { kind: "avatar", key: "telegram:user-id" };
  vi.mocked(fetchManagedRecord).mockRejectedValueOnce(new Error("暂时无法读取"));
  render(<ManagedRecordDialog locator={avatarLocator} onClose={vi.fn()} onChanged={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法读取");
  vi.mocked(fetchManagedRecord).mockResolvedValueOnce({
    locator: avatarLocator,
    revision: "v1",
    data: { data_uri: "data:image/png;base64,iVBORw0KGgo=" },
  });
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  fireEvent.click(await screen.findByRole("button", { name: "放大头像" }));
  const preview = screen.getByRole("dialog", { name: "头像预览" });
  expect(within(preview).getByAltText("放大的缓存头像")).toBeInTheDocument();
  fireEvent.keyDown(preview, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "头像预览" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "头像缓存详情" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "放大头像" }));
  fireEvent.click(
    within(screen.getByRole("dialog", { name: "头像预览" })).getByRole("button", {
      name: "返回记录",
    }),
  );
  expect(screen.getByRole("dialog", { name: "头像缓存详情" })).toBeInTheDocument();
  vi.mocked(copyToClipboard).mockResolvedValue(false);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "复制缓存键" })));
  expect(screen.getByRole("status")).toHaveTextContent("复制失败");
});
it("导入保留完整数据格式，提交期间禁止再次提交或关闭", async () => {
  const close = vi.fn();
  let resolve!: () => void;
  vi.mocked(mutateManagedRecord).mockReturnValue(
    new Promise<void>((r) => {
      resolve = r;
    }),
  );
  render(
    <ManagedRecordDialog locator={null} importKind="history" onClose={close} onChanged={vi.fn()} />,
  );
  fireEvent.change(screen.getByRole("textbox"), {
    target: {
      value: JSON.stringify({
        locator: { kind: "history", key: "new" },
        data: { unknown: [false, 0] },
      }),
    },
  });
  fireEvent.click(screen.getByRole("button", { name: "导入为新记录" }));
  expect(screen.getByRole("button", { name: "正在保存…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "关闭记录" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  expect(close).not.toHaveBeenCalled();
  await act(async () => resolve());
  expect(close).toHaveBeenCalledOnce();
});
