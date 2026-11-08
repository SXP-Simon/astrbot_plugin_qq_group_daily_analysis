import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CheckpointDetailModal } from "../CheckpointDetailModal";
import { copyToClipboard } from "../../../../../shared/lib/clipboard";
vi.mock("../../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const detail = {
  group_id: "discord:string-id",
  date_str: "2026-11-07",
  stage_name: "LLM_ANALYSIS",
  trace_id: "trace-string-id",
  data_size_bytes: 0,
  data: { nested: { unknown: [0, false, "用户内容"] } },
};
it("完整展示产物和任务编号，复制失败不会提示成功", async () => {
  vi.mocked(copyToClipboard).mockResolvedValue(false);
  render(<CheckpointDetailModal open onClose={() => {}} loading={false} ckptDetail={detail} />);
  expect(screen.getByText("discord:string-id")).toBeInTheDocument();
  expect(screen.getByText("0 B")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "阶段产物数据" })).toHaveTextContent('"unknown"');
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "复制产物数据" })));
  expect(copyToClipboard).toHaveBeenCalledWith(JSON.stringify(detail.data, null, 2));
  expect(screen.getByRole("status")).toHaveTextContent("复制失败");
  vi.mocked(copyToClipboard).mockResolvedValue(true);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "复制任务编号" })));
  expect(copyToClipboard).toHaveBeenLastCalledWith(detail.trace_id);
  expect(screen.getByRole("status")).toHaveTextContent("已复制任务编号");
});
it("读取错误可重试，缺失产物禁用复制，按天快照有明确说明", () => {
  const retry = vi.fn();
  const { rerender } = render(
    <CheckpointDetailModal
      open
      onClose={() => {}}
      loading={false}
      ckptDetail={detail}
      error="已过期"
      onRetry={retry}
    />,
  );
  expect(screen.getByRole("button", { name: "复制产物数据" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  expect(retry).toHaveBeenCalledOnce();
  rerender(
    <CheckpointDetailModal
      open
      onClose={() => {}}
      loading={false}
      ckptDetail={{ ...detail, trace_id: "", data: undefined }}
    />,
  );
  expect(screen.getByText("按天保存，未关联任务")).toBeInTheDocument();
  expect(screen.getByText("未记录产物数据。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制产物数据" })).toBeDisabled();
});
it("切换快照后迟到的复制反馈不会显示在新详情", async () => {
  let resolve!: (value: boolean) => void;
  vi.mocked(copyToClipboard).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const { rerender } = render(
    <CheckpointDetailModal open onClose={() => {}} loading={false} ckptDetail={detail} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "复制产物数据" }));
  rerender(
    <CheckpointDetailModal
      open
      onClose={() => {}}
      loading={false}
      ckptDetail={{ ...detail, trace_id: "new" }}
    />,
  );
  await act(async () => resolve(true));
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
});
