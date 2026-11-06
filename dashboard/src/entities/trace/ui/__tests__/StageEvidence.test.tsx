import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { SpanAlerts } from "../SpanAlerts";
import { LlmAttemptsTable } from "../LlmAttemptsTable";

it("仅有话题数为零不能断言全部分析无产出或 Provider 故障", () => {
  const view = render(
    <SpanAlerts stageName="LLM_ANALYSIS" status="success" payload={{ topics_count: 0 }} />,
  );
  expect(screen.queryByLabelText("阶段提示")).not.toBeInTheDocument();
  view.rerender(
    <SpanAlerts
      stageName="LLM_ANALYSIS"
      status="success"
      payload={{ topics_count: 0, user_titles_count: 2, enabled_features: { user_titles: true } }}
    />,
  );
  expect(screen.queryByLabelText("阶段提示")).not.toBeInTheDocument();
  view.rerender(
    <SpanAlerts
      stageName="LLM_ANALYSIS"
      status="running"
      payload={{
        topics_count: 0,
        user_titles_count: 0,
        golden_quotes_count: 0,
        chat_quality_review: false,
        enabled_features: { topics: true },
      }}
    />,
  );
  expect(screen.queryByLabelText("阶段提示")).not.toBeInTheDocument();
});

it("只有完整关闭记录才提示模块未开启，真实空结果保留排查入口", () => {
  const view = render(
    <SpanAlerts stageName="LLM_ANALYSIS" status="success" payload={{ enabled_features: {} }} />,
  );
  expect(screen.queryByText("未启用分析模块")).not.toBeInTheDocument();
  view.rerender(
    <SpanAlerts
      stageName="LLM_ANALYSIS"
      status="skipped"
      payload={{
        enabled_features: {
          topics: false,
          user_titles: false,
          golden_quotes: false,
          chat_quality: false,
        },
      }}
    />,
  );
  expect(screen.getByText("未启用分析模块")).toBeVisible();
  view.rerender(
    <SpanAlerts
      stageName="LLM_ANALYSIS"
      status="success"
      payload={{
        topics_count: 0,
        user_titles_count: 0,
        golden_quotes_count: 0,
        chat_quality_review: false,
        enabled_features: { topics: true },
      }}
    />,
  );
  expect(screen.getByText("未记录分析结果")).toBeVisible();
  expect(screen.queryByText(/Provider/)).not.toBeInTheDocument();
});

it("保留恢复原因与结构化子任务错误，不从单个取消阶段推断全任务停止", () => {
  render(
    <SpanAlerts
      stageName="TYPST_BASIC_RECOVERY"
      status="cancelled"
      payload={{
        mode: "basic",
        reason: "模板编译失败",
        failure_reason: "缺少字体",
        subtask_errors: [{ area: "topics", error: "timeout" }, "网络断开"],
      }}
    />,
  );
  expect(screen.getByText("该阶段已停止。")).toBeVisible();
  expect(screen.queryByText(/后续步骤已停止/)).not.toBeInTheDocument();
  expect(screen.getByText("模板编译失败")).toBeVisible();
  expect(screen.getByText("缺少字体")).toBeVisible();
  expect(screen.getByText(/"area":"topics"/)).toBeVisible();
  expect(screen.getByText("网络断开")).toBeVisible();
});

it("模型调用区分运行、失败、取消、跳过和未记录，未知耗时不是零", () => {
  render(
    <LlmAttemptsTable
      attempts={[
        { status: "running", area: "topics", duration_ms: null },
        {
          status: "success",
          area: "topics#schema_retry_2",
          provider_id: "backup-model",
          model: "model",
          attempt: 3,
          is_fallback: true,
          duration_ms: 0,
        },
        { status: "failed", error: "HTTP 503", duration_ms: Infinity },
        { status: "cancelled", error: "用户停止" },
        { status: "skipped" },
        { status: "future_status" },
      ]}
    />,
  );
  const rows = screen.getAllByRole("listitem");
  expect(within(rows[0]).getByText("请求中")).toBeVisible();
  expect(within(rows[0]).getByText("耗时未记录")).toBeVisible();
  expect(within(rows[1]).getByText("0ms")).toBeVisible();
  expect(within(rows[1]).getByText("备用 Provider")).toBeVisible();
  expect(within(rows[1]).getByText("格式修复第 2 次")).toBeVisible();
  expect(within(rows[1]).getByText("调用次数 3")).toBeVisible();
  expect(within(rows[1]).getByText("backup-model")).toBeVisible();
  expect(within(rows[1]).queryByText(/backup-model \/ model/)).not.toBeInTheDocument();
  expect(within(rows[2]).getByText("失败")).toBeVisible();
  expect(within(rows[2]).getByText("HTTP 503")).toBeVisible();
  expect(within(rows[3]).getByText("已停止")).toBeVisible();
  expect(within(rows[4]).getByText("已跳过")).toBeVisible();
  expect(within(rows[5]).getByText("状态未记录")).toBeVisible();
  expect(screen.queryByText(/Infinity|NaN|default/)).not.toBeInTheDocument();
});

it("模型元数据结构异常时仍保留可识别错误", () => {
  render(
    <LlmAttemptsTable
      attempts={[
        {
          area: {},
          provider_id: {},
          status: "failed",
          error: "服务不可用",
          is_fallback: "false",
          attempt: -1,
        },
      ]}
    />,
  );
  expect(screen.getByText("服务不可用")).toBeVisible();
  expect(screen.queryByText("备用 Provider")).not.toBeInTheDocument();
  expect(screen.queryByText(/object Object|调用次数/)).not.toBeInTheDocument();
});
