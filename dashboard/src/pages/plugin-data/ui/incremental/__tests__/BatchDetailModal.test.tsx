import serializedBatch from "@/pages/plugin-data/model/__tests__/fixtures/incrementalBatch.json";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BatchDetailModal } from "@/pages/plugin-data/ui/incremental/BatchDetailModal";
import type { IncrementalBatchItem } from "@/entities/plugin-data/model/types";
import { copyToClipboard } from "@/shared/lib/clipboard";
vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const batch: IncrementalBatchItem = {
  group_id: "telegram:-100001",
  batch_id: "batch-long-string-id",
  timestamp: 1794000000,
  messages_count: 10,
  characters_count: 90,
  topics_count: 1,
  token_usage: { total_tokens: 0, prompt_tokens: 0, completion_tokens: 0 },
  chat_quality_review: {
    title: "轻松交流",
    summary: "大家分享日常",
    dimensions: [{ name: "信息交流", percentage: 0, comment: "没有技术话题" }],
  },
  topics: [
    {
      topic: "周末出游",
      detail: "[alice] 分享了徒步路线",
      contributors: ["小林"],
      contributor_ids: ["alice"],
    },
  ],
  golden_quotes: [
    {
      content: "出门才知道天气真好",
      sender: "小林",
      user_id: "alice",
      reason: "说出了出游的轻松心情",
    },
  ],
  extension: { preserved: true },
};

it("批次详情保留评价、话题、金句、零消耗与完整扩展数据", async () => {
  vi.mocked(copyToClipboard).mockResolvedValue(true);
  render(<BatchDetailModal open onClose={vi.fn()} batchDetail={batch} loading={false} />);
  expect(screen.getByRole("dialog")).toHaveAccessibleName("增量批次详情");
  expect(screen.getByText("大家分享日常")).toBeVisible();
  expect(screen.getByText("信息交流 · 0%")).toBeVisible();
  expect(screen.getByText("[alice] 分享了徒步路线")).toBeVisible();
  expect(screen.getByText("出门才知道天气真好")).toBeVisible();
  expect(screen.getByText("参与者：小林")).toBeVisible();
  expect(screen.queryByText(/热度|℃/)).not.toBeInTheDocument();
  expect(screen.getByText("说出了出游的轻松心情")).toBeVisible();
  expect(screen.getByText("0 / 0")).toBeVisible();
  fireEvent.click(screen.getByText("完整批次数据（JSON）"));
  expect(screen.getByText(/"preserved": true/)).toBeVisible();
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "复制完整 JSON" })));
  expect(copyToClipboard).toHaveBeenCalledWith(JSON.stringify(batch, null, 2));
  expect(screen.getByText("已复制完整 JSON")).toBeVisible();
});

it("读取失败不暴露列表摘要为完整数据，可重试且加载期间不可复制", () => {
  const retry = vi.fn();
  const { rerender } = render(
    <BatchDetailModal
      open
      onClose={vi.fn()}
      batchDetail={batch}
      loading
      error="批次读取失败"
      onRetry={retry}
    />,
  );
  expect(screen.getByRole("button", { name: "复制完整 JSON" })).toBeDisabled();
  expect(screen.getByText("正在读取批次详情…")).toBeVisible();
  rerender(
    <BatchDetailModal
      open
      onClose={vi.fn()}
      batchDetail={batch}
      loading={false}
      error="批次读取失败"
      onRetry={retry}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("批次读取失败");
  expect(screen.queryByText("周末出游")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  expect(retry).toHaveBeenCalledOnce();
});

it("复制失败准确反馈，切换批次后旧复制回执失效", async () => {
  let resolve!: (value: boolean) => void;
  vi.mocked(copyToClipboard)
    .mockResolvedValueOnce(false)
    .mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
  const { rerender } = render(
    <BatchDetailModal open onClose={vi.fn()} batchDetail={batch} loading={false} />,
  );
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "复制完整 JSON" })));
  expect(screen.getByText("复制失败，可展开完整数据后手动复制。")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "复制批次编号" }));
  rerender(
    <BatchDetailModal
      open
      onClose={vi.fn()}
      batchDetail={{ ...batch, batch_id: "next" }}
      loading={false}
    />,
  );
  await act(async () => resolve(true));
  expect(screen.queryByText("已复制批次编号")).not.toBeInTheDocument();
});

it("旧评价字符串与未知结构仍可查看，关闭回调保留", () => {
  const close = vi.fn();
  const { rerender } = render(
    <BatchDetailModal
      open
      onClose={close}
      batchDetail={{ ...batch, chat_quality_review: "旧评价正文" }}
      loading={false}
    />,
  );
  expect(screen.getByText("旧评价正文")).toBeVisible();
  rerender(
    <BatchDetailModal
      open
      onClose={close}
      batchDetail={{ ...batch, chat_quality_review: { dimensions: "旧格式", extra: "扩展评价" } }}
      loading={false}
    />,
  );
  expect(screen.getAllByText(/"extra": "扩展评价"/)[0]).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "关闭详情" }));
  expect(close).toHaveBeenCalledOnce();
});

it("真实批次序列化结构能展示话题摘要、参与者和金句作者", () => {
  render(<BatchDetailModal open onClose={vi.fn()} batchDetail={serializedBatch} loading={false} />);
  expect(screen.getByText("周末出游")).toBeVisible();
  expect(screen.getByText("[alice] 分享了徒步路线")).toBeVisible();
  expect(screen.getByText("参与者：小林")).toBeVisible();
  expect(screen.getByText("出门才知道天气真好")).toBeVisible();
  expect(screen.getByText("说出了出游的轻松心情")).toBeVisible();
  expect(screen.queryByText(/热度|℃|未命名话题/)).not.toBeInTheDocument();
});
