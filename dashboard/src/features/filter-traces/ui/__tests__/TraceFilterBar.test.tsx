import { useState, type ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TraceFilterBar } from "@/features/filter-traces/ui/TraceFilterBar";

function props(): ComponentProps<typeof TraceFilterBar> {
  return {
    search: "",
    groups: [],
    loading: false,
    onSearchChange: vi.fn(),
    onGroupChange: vi.fn(),
    onPlatformChange: vi.fn(),
    onStatusChange: vi.fn(),
    onTriggerTypeChange: vi.fn(),
    onDateRangeChange: vi.fn(),
    onRefresh: vi.fn(),
  };
}

it("日期使用本地完整日边界，清空一端保留另一端，倒置范围有可读错误", () => {
  const base = props();
  function Controlled() {
    const [range, setRange] = useState<[number, number] | null>(null);
    return (
      <TraceFilterBar
        {...base}
        dateRange={range}
        onDateRangeChange={(value) => {
          base.onDateRangeChange(value);
          setRange(value);
        }}
      />
    );
  }
  render(<Controlled />);
  const start = screen.getByLabelText("开始日期");
  const end = screen.getByLabelText("结束日期");
  fireEvent.change(start, { target: { value: "2026-11-07" } });
  expect(start).toHaveValue("2026-11-07");
  fireEvent.change(end, { target: { value: "2026-11-08" } });
  expect(base.onDateRangeChange).toHaveBeenLastCalledWith([
    new Date("2026-11-07T00:00:00").getTime() / 1000,
    new Date("2026-11-08T23:59:59.999").getTime() / 1000,
  ]);
  fireEvent.change(end, { target: { value: "" } });
  expect(start).toHaveValue("2026-11-07");
  expect(base.onDateRangeChange).toHaveBeenLastCalledWith(null);
  const calls = vi.mocked(base.onDateRangeChange).mock.calls.length;
  fireEvent.change(end, { target: { value: "2026-11-06" } });
  expect(base.onDateRangeChange).toHaveBeenCalledTimes(calls);
  expect(screen.getByRole("alert")).toHaveTextContent("结束日期不能早于开始日期");
  expect(end).toHaveAccessibleDescription("结束日期不能早于开始日期。");
  fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
  expect(start).toHaveValue("");
  expect(end).toHaveValue("");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("搜索、群聊、状态与触发方式都可选择，刷新禁用时不重复操作", () => {
  const base = {
    ...props(),
    groups: [{ group_id: "photo-group", group_name: "示例摄影群", platform: "telegram" }],
  };
  const view = render(<TraceFilterBar {...base} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "摄影" } });
  expect(base.onSearchChange).toHaveBeenCalledWith("摄影");
  fireEvent.click(screen.getByRole("button", { name: "选择群聊：全部群聊" }));
  fireEvent.click(screen.getByRole("button", { name: "示例摄影群（photo-group） · Telegram" }));
  expect(base.onGroupChange).toHaveBeenCalledWith("photo-group", "telegram");
  fireEvent.change(screen.getByLabelText("执行状态"), { target: { value: "failed" } });
  fireEvent.change(screen.getByLabelText("触发方式"), { target: { value: "rerender_report" } });
  expect(base.onStatusChange).toHaveBeenCalledWith("failed");
  expect(base.onTriggerTypeChange).toHaveBeenCalledWith("rerender_report");
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  expect(base.onRefresh).toHaveBeenCalledTimes(1);
  view.rerender(<TraceFilterBar {...base} loading />);
  expect(screen.getByRole("button", { name: "刷新" })).toBeDisabled();
});

it("统计页可以不提供触发筛选和统一重置，外部日期范围仍可同步", () => {
  const base = { ...props(), onTriggerTypeChange: undefined };
  const view = render(<TraceFilterBar {...base} />);
  expect(screen.queryByLabelText("触发方式")).not.toBeInTheDocument();
  view.rerender(
    <TraceFilterBar
      {...base}
      dateRange={[
        new Date("2026-11-01T00:00:00").getTime() / 1000,
        new Date("2026-11-02T23:59:59").getTime() / 1000,
      ]}
    />,
  );
  expect(screen.getByLabelText("开始日期")).toHaveValue("2026-11-01");
  fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
  expect(base.onSearchChange).toHaveBeenCalledWith("");
  expect(base.onGroupChange).toHaveBeenCalledWith(undefined);
  expect(base.onStatusChange).toHaveBeenCalledWith(undefined);
  expect(base.onDateRangeChange).toHaveBeenCalledWith(null);
});
