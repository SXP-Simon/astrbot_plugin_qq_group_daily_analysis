import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { TraceRecord } from "@/entities/trace/model/types";
import { TraceTable } from "@/widgets/trace-table/TraceTable";

const trace: TraceRecord = {
  trace_id: "example-a",
  group_id: "group-a",
  group_name: "示例摄影群",
  platform: "telegram",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 100,
};
const callbacks = () => ({ onPageChange: vi.fn(), onSortChange: vi.fn(), onViewTrace: vi.fn() });

it("保留四种排序、分页与详情入口，未知耗时和消息数不伪装成零", () => {
  const actions = callbacks();
  render(
    <TraceTable
      traces={[trace]}
      total={31}
      loading={false}
      page={1}
      pageSize={15}
      sortField="started_at"
      sortOrder="desc"
      {...actions}
    />,
  );
  for (const [label, field] of [
    ["耗时", "duration_ms"],
    ["模型消耗", "total_tokens"],
    ["消息留存率", "compression_ratio"],
    ["开始时间", "started_at"],
  ]) {
    fireEvent.click(screen.getByRole("button", { name: `按${label}排序` }));
    expect(actions.onSortChange).toHaveBeenLastCalledWith(field);
  }
  expect(screen.getByRole("button", { name: "按开始时间排序" }).closest("th")).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  const row = screen.getByRole("row", { name: /示例摄影群/ });
  expect(within(row).getByText("有效 未记录 / 拉取 未记录")).toBeInTheDocument();
  expect(within(row).getAllByText("未记录").length).toBeGreaterThanOrEqual(2);
  fireEvent.click(within(row).getByRole("button", { name: "详情" }));
  fireEvent.click(within(row).getByRole("button", { name: "example-a" }));
  expect(actions.onViewTrace).toHaveBeenCalledTimes(2);
  expect(actions.onViewTrace).toHaveBeenLastCalledWith("example-a");
  fireEvent.click(screen.getByRole("button", { name: "第 3 页" }));
  expect(actions.onPageChange).toHaveBeenCalledWith(3, 15);
});

it("成功任务可标记警告，但不能覆盖失败和取消；零值、全量恢复原因仍可查看", () => {
  const records: TraceRecord[] = [
    {
      ...trace,
      duration_ms: 0,
      raw_message_count: 0,
      cleaned_message_count: 0,
      compression_ratio: 0,
      extra: { has_warnings: true, fallback_to_fresh_run: true },
    },
    { ...trace, trace_id: "failed", status: "failed", extra: { has_warnings: true } },
    { ...trace, trace_id: "cancelled", status: "cancelled", extra: { has_warnings: true } },
  ];
  render(
    <TraceTable
      traces={records}
      total={3}
      loading={false}
      page={1}
      pageSize={15}
      sortField="started_at"
      sortOrder="desc"
      {...callbacks()}
    />,
  );
  const rows = screen.getAllByRole("row").slice(1);
  expect(within(rows[0]).getByText("警告")).toBeInTheDocument();
  expect(within(rows[1]).getByText("失败")).toBeInTheDocument();
  expect(within(rows[2]).getByText("已中止")).toBeInTheDocument();
  expect(within(rows[0]).getByText("0ms")).toBeInTheDocument();
  expect(within(rows[0]).getByText("0%")).toBeInTheDocument();
  expect(within(rows[0]).getByText("有效 0 / 拉取 0")).toBeInTheDocument();
  fireEvent.click(screen.getByText("已重新全量分析"));
  expect(screen.getByText(/未找到历史快照/).closest("details")).toHaveAttribute("open");
});

it("加载与空数据分别展示，已知总数时读取期间允许继续翻页", () => {
  const base = {
    traces: [],
    total: 0,
    page: 1,
    pageSize: 15,
    sortField: "started_at" as const,
    sortOrder: "desc" as const,
    ...callbacks(),
  };
  const view = render(<TraceTable {...base} loading />);
  expect(screen.getByRole("status")).toHaveTextContent("正在更新分析记录");
  expect(screen.queryByText("暂无符合条件的分析记录")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  view.rerender(<TraceTable {...base} total={45} loading />);
  expect(screen.getByRole("button", { name: "下一页" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(base.onPageChange).toHaveBeenLastCalledWith(2, 15);
  view.rerender(<TraceTable {...base} loading={false} />);
  expect(screen.getByText("暂无符合条件的分析记录")).toBeInTheDocument();
});
