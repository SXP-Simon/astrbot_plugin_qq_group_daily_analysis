import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { TraceSummaryCard } from "../TraceSummaryCard";
import { TraceLogViewer } from "../TraceLogViewer";
import { TraceDrawer } from "../../TraceDrawer";
import { fetchTraceDetail } from "../../../../entities/trace/api/traceApi";
import { fetchReportContent } from "../../../../entities/report/api/reportApi";
import { copyToClipboard } from "../../../../shared/lib/clipboard";
import type { TraceRecord } from "../../../../entities/trace/model/types";
import type { PluginLogItem } from "../../../../entities/log/model/types";

vi.mock("../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
vi.mock("../../../../entities/trace/api/traceApi", () => ({
  fetchTraceDetail: vi.fn(),
  resumeTraceTask: vi.fn(),
  fetchProviderList: vi.fn().mockResolvedValue([]),
}));
vi.mock("../../../../entities/report/api/reportApi", () => ({
  fetchReportContent: vi.fn(),
  fetchReportTemplates: vi.fn().mockResolvedValue([]),
}));
vi.mock("../../../../entities/log/api/logApi", () => ({
  fetchTraceLogs: vi.fn().mockResolvedValue([]),
}));
vi.mock("echarts-for-react", () => ({ default: () => <div>图表</div> }));

const trace: TraceRecord = {
  trace_id: "example",
  group_id: "group-字符串",
  group_name: "示例群聊",
  platform: "discord",
  started_at: 1,
  status: "succeeded",
  trigger_type: "manual",
  duration_ms: 0,
  report_files: [
    { filename: "example.html", format: "html", size_bytes: 1500 },
    { filename: "example.html" },
  ],
};
const log: PluginLogItem = {
  id: "log",
  timestamp: 1,
  time_str: "2026-11-06 12:00:00",
  level: "ERROR",
  logger_name: "example",
  tag: "Render",
  message: "示例失败记录",
  raw: "原始日志文本",
  location: "render:10",
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchTraceDetail).mockResolvedValue(trace);
  vi.mocked(copyToClipboard).mockResolvedValue(true);
  vi.mocked(fetchReportContent).mockResolvedValue({
    filename: "example.html",
    size_bytes: 1500,
    modified_at: 1,
    is_html: true,
    html_content: "<h1>示例报告</h1>",
  });
});

it("摘要保留真实零耗时、平台与字符串群号，文件去重并保留预览下载", () => {
  const preview = vi.fn();
  const download = vi.fn();
  render(<TraceSummaryCard trace={trace} onPreviewFile={preview} onDownloadFile={download} />);
  expect(screen.getByText("0ms")).toBeVisible();
  fireEvent.click(screen.getByText("任务与消耗明细"));
  expect(screen.getByText("group-字符串")).toBeVisible();
  expect(screen.getByText("discord")).toBeVisible();
  expect(screen.getAllByText("example.html")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "预览" }));
  fireEvent.click(screen.getByRole("button", { name: "下载" }));
  expect(preview).toHaveBeenCalledWith("example.html", true);
  expect(download).toHaveBeenCalledWith("example.html", true);
});

it("兼容历史产物记录，忽略无效条目；快照缺失不声称报告已经送达", () => {
  render(
    <TraceSummaryCard
      trace={{
        ...trace,
        duration_ms: null,
        report_files: undefined,
        extra: {
          fallback_to_fresh_run: true,
          report_files: [null, "invalid", { filename: "漫画_example.png" }],
        },
      }}
      onPreviewFile={vi.fn()}
      onDownloadFile={vi.fn()}
    />,
  );
  expect(screen.getAllByText("未记录").length).toBeGreaterThan(0);
  expect(screen.getByText("漫画_example.png")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("重新拉取消息并分析");
  expect(screen.queryByText(/完成.*交付/)).not.toBeInTheDocument();
});

it("日志复制尊重真实结果，并保留错误级别、来源和快捷键", async () => {
  vi.mocked(copyToClipboard).mockResolvedValueOnce(false);
  render(<TraceLogViewer logs={[{ ...log, function_name: "Renderer.generate" }]} />);
  expect(screen.getByText("[ERROR]")).toBeVisible();
  expect(screen.getByText("[render:10]")).toBeVisible();
  expect(screen.getByText("[Renderer.generate()]")).toBeVisible();
  expect(screen.getByText("[报告与模板]")).toHaveAttribute("title", "Render");
  fireEvent.click(screen.getByRole("button", { name: "复制日志" }));
  await screen.findByText("无法复制，请手动选择日志内容。");
  expect(copyToClipboard).toHaveBeenCalledWith("原始日志文本");
  fireEvent.keyDown(screen.getByRole("region", { name: "任务日志内容" }), {
    key: "a",
    ctrlKey: true,
  });
  await screen.findByText("已复制日志");
});

it("正式详情保留完整记录并可打开嵌套报告预览，关闭返回预览按钮", async () => {
  render(<TraceDrawer traceId="example" open onClose={vi.fn()} />);
  const detail = await screen.findByRole("dialog", { name: "示例群聊" });
  expect(within(detail).getByText("执行过程")).toBeVisible();
  fireEvent.click(screen.getByText("完整任务记录"));
  expect(screen.getByText(/"trace_id": "example"/)).toBeVisible();
  const preview = screen.getByRole("button", { name: "预览" });
  preview.focus();
  fireEvent.click(preview);
  const reportDialog = await screen.findByRole("dialog", { name: "报告预览" });
  await waitFor(() =>
    expect(within(reportDialog).getByTitle("example.html")).toHaveAttribute(
      "srcdoc",
      "<h1>示例报告</h1>",
    ),
  );
  fireEvent.click(within(reportDialog).getByRole("button", { name: "关闭预览" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: "报告预览" })).not.toBeInTheDocument(),
  );
  expect(preview).toHaveFocus();
});
