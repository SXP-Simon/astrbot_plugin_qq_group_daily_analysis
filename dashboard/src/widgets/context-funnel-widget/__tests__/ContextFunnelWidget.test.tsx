import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ContextFunnelWidget } from "@/widgets/context-funnel-widget/ContextFunnelWidget";

it("读取、有效、过滤数量与留存率对应实际记录，不把占比当作进度", () => {
  render(
    <ContextFunnelWidget
      metrics={{
        raw_message_count: 100,
        cleaned_message_count: 75,
        compression_ratio: 0.75,
        incremental_batches: 3,
        window_size: 24,
      }}
    />,
  );
  expect(screen.getByText("75%")).toBeVisible();
  expect(screen.getByText("过滤消息").parentElement).toHaveTextContent("25 条");
  expect(screen.getByText("采样窗口").parentElement).toHaveTextContent("24 条");
  expect(screen.getByText("增量批次").parentElement).toHaveTextContent("3 批");
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

it("缺失与零值区分，零批次不改为一批，无效数值不显示负数或超过百分百", () => {
  const view = render(<ContextFunnelWidget metrics={{}} />);
  expect(screen.getByText("读取消息").parentElement).toHaveTextContent("未记录");
  expect(screen.getByText("增量批次").parentElement).toHaveTextContent("未记录");
  view.rerender(
    <ContextFunnelWidget
      metrics={{
        raw_message_count: 0,
        cleaned_message_count: 0,
        compression_ratio: 0,
        incremental_batches: 0,
      }}
    />,
  );
  expect(screen.getByText("0%")).toBeVisible();
  expect(screen.getByText("增量批次").parentElement).toHaveTextContent("0 批");
  view.rerender(
    <ContextFunnelWidget
      metrics={{
        raw_message_count: 10,
        cleaned_message_count: 11,
        compression_ratio: 1.1,
        window_size: -1,
      }}
    />,
  );
  expect(screen.getByText("过滤消息").parentElement).toHaveTextContent("未记录");
  expect(screen.getByText("采样窗口").parentElement).toHaveTextContent("未记录");
  expect(screen.getByText(/记录不一致/)).toBeVisible();
  expect(screen.queryByText("110%")).not.toBeInTheDocument();
});
