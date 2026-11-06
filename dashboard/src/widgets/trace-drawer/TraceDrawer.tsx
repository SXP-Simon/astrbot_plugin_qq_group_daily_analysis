import React, { useState } from "react";
import {
  Drawer,
  Tag,
  Alert,
  Typography,
  Spin,
  Collapse,
  Space,
  Button,
  message,
  theme,
} from "antd";
import { ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { resumeTraceTask } from "../../entities/trace/api/traceApi";
import { fetchReportContent } from "../../entities/report/api/reportApi";
import { ReportItem } from "../../entities/report/model/types";
import { ReportPreviewModal } from "../report-preview-modal/ReportPreviewModal";
import { StatusTag } from "../../shared/ui/StatusTag";
import { SpanTimeline } from "../../entities/trace/ui/SpanTimeline";
import { formatStageName } from "../../shared/lib/formatters";
import { ResumeTaskModal } from "../../features/resume-task/ui/ResumeTaskModal";
import { TraceMetricsChart } from "../../entities/trace/ui/TraceMetricsChart";
import { TraceLogViewer } from "./ui/TraceLogViewer";
import { TraceSummaryCard } from "./ui/TraceSummaryCard";

import { useTraceDetail } from "./model/useTraceDetail";

const { Text, Paragraph } = Typography;

interface TraceDrawerProps {
  traceId: string | null;
  open: boolean;
  onClose: () => void;
}

export const TraceDrawer: React.FC<TraceDrawerProps> = ({ traceId, open, onClose }) => {
  const { token } = theme.useToken();
  const { trace, logs, loading, refreshing, error, logsError, effectiveStatus, refresh } =
    useTraceDetail(traceId, open);
  const [resuming, setResuming] = useState(false);
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  const handleConfirmResume = async (selectedProvider?: string, selectedTemplate?: string) => {
    if (!traceId) return;
    setResuming(true);
    try {
      await resumeTraceTask(traceId, selectedProvider, selectedTemplate);
      message.success("已成功触发断点续跑任务，正在恢复分析...");
      setResumeModalOpen(false);
      refresh();
    } catch (e) {
      message.error(`触发续跑失败: ${e}`);
    } finally {
      setResuming(false);
    }
  };

  const handlePreviewFile = async (filename: string, isHtml: boolean) => {
    const baseItem: ReportItem = {
      filename,
      size_bytes: 0,
      modified_at: Date.now() / 1000,
      is_html: isHtml,
      group_id: trace?.group_id,
      group_name: trace?.group_name,
      platform: trace?.platform,
      trace_id: trace?.trace_id,
    };
    setPreviewReport(baseItem);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const data = await fetchReportContent(filename);
      if (data) {
        setPreviewReport((prev) => ({
          ...(prev || baseItem),
          ...data,
        }));
      }
    } catch {
      message.error("加载产物报告文件失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownloadFile = async (filename: string, isHtml: boolean) => {
    try {
      const data = await fetchReportContent(filename);
      if (!data) {
        message.error("获取下载文件失败");
        return;
      }
      let href = data.data_url;
      let cleanupBlobUrl: string | null = null;
      if (isHtml && data.html_content) {
        const blob = new Blob([data.html_content], { type: "text/html;charset=utf-8" });
        href = URL.createObjectURL(blob);
        cleanupBlobUrl = href;
      }
      if (!href) {
        message.error("未获取到下载链接");
        return;
      }
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      if (cleanupBlobUrl) {
        URL.revokeObjectURL(cleanupBlobUrl);
      }
    } catch {
      message.error("下载文件失败");
    }
  };

  return (
    <Drawer
      title={
        <Space size="middle">
          <span style={{ fontSize: 16, fontWeight: 600 }}>任务执行详情</span>
          {trace && <StatusTag status={effectiveStatus} />}
        </Space>
      }
      extra={
        <Space size="small">
          {trace && trace.status !== "running" && (
            <Button
              size="small"
              type="primary"
              ghost
              icon={<SyncOutlined spin={resuming} />}
              loading={resuming}
              onClick={() => setResumeModalOpen(true)}
            >
              幂等续跑
            </Button>
          )}
          <Button
            size="small"
            type="text"
            icon={<ReloadOutlined spin={loading || refreshing} />}
            onClick={refresh}
            disabled={loading || refreshing}
          >
            刷新
          </Button>
        </Space>
      }
      placement="right"
      width={600}
      onClose={onClose}
      open={open}
      destroyOnHidden
    >
      {error && <Alert type="error" showIcon message={error} />}
      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin tip="正在加载任务详情..." />
        </div>
      ) : trace ? (
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {/* 运行中状态提示 */}
          {trace.status === "running" && (
            <Alert
              type="info"
              showIcon
              icon={<SyncOutlined spin />}
              message="任务正在执行中"
              description={
                <span>
                  当前阶段：
                  <Tag color="processing" style={{ margin: "0 4px" }}>
                    {trace.current_stage ? formatStageName(trace.current_stage) : "准备中"}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    （详情自动更新，任务结束后停止刷新）
                  </Text>
                </span>
              }
            />
          )}

          {/* 跳过提示 */}
          {trace.status === "skipped" && (
            <Alert
              type="info"
              showIcon
              message="定时/增量分析已安全跳过"
              description={
                <Paragraph
                  ellipsis={{ rows: 2, expandable: true, symbol: "展开详情" }}
                  style={{ marginBottom: 0, fontSize: 13 }}
                >
                  {trace.error_message ||
                    "未达到分析触发阈值或未满足执行条件，本次调度已安全跳过，未消耗任何 Token。"}
                </Paragraph>
              }
            />
          )}

          {/* 错误警告与快速重试 */}
          {trace.status === "failed" && (
            <Alert
              type="error"
              showIcon
              message={
                trace.error_stage
                  ? `在【${formatStageName(trace.error_stage)}】阶段发生异常`
                  : "分析过程发生异常"
              }
              description={
                <div>
                  <Paragraph
                    ellipsis={{ rows: 2, expandable: true, symbol: "展开详情" }}
                    style={{ marginBottom: 4 }}
                  >
                    {trace.error_message || "未知错误"}
                  </Paragraph>
                  <div style={{ marginTop: 8, marginBottom: 8 }}>
                    <Button
                      type="primary"
                      size="small"
                      danger
                      ghost
                      icon={<SyncOutlined spin={resuming} />}
                      loading={resuming}
                      onClick={() => setResumeModalOpen(true)}
                    >
                      从 Checkpoint 幂等续跑此任务
                    </Button>
                  </div>
                  {trace.stack_trace && (
                    <Collapse
                      size="small"
                      ghost
                      items={[
                        {
                          key: "stack_trace",
                          label: <span style={{ fontSize: 11 }}>查看异常堆栈 (Stack Trace)</span>,
                          children: (
                            <pre
                              style={{
                                fontSize: 11,
                                fontFamily:
                                  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
                                background: token.colorFillAlter,
                                color: token.colorText,
                                border: `1px solid ${token.colorBorderSecondary}`,
                                padding: 8,
                                borderRadius: 4,
                                maxHeight: 200,
                                overflow: "auto",
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-all",
                              }}
                            >
                              {trace.stack_trace}
                            </pre>
                          ),
                        },
                      ]}
                    />
                  )}
                </div>
              }
            />
          )}

          {/* 基本信息与消耗概览 */}
          <TraceSummaryCard
            trace={trace}
            onPreviewFile={handlePreviewFile}
            onDownloadFile={handleDownloadFile}
          />

          {/* 全链路性能指标与运行期资源观测图表 */}
          <TraceMetricsChart trace={trace} />

          {/* 执行阶段时间线 */}
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              执行生命周期阶段 (Spans)
            </div>
            <SpanTimeline
              spans={trace.spans || []}
              totalDurationMs={trace.duration_ms ?? undefined}
              currentStage={trace.current_stage ?? undefined}
              taskStatus={trace.status}
            />
          </div>

          {/* 专属执行日志流 */}
          {logsError && <Alert type="warning" showIcon message={logsError} />}
          <TraceLogViewer logs={logs} />
        </Space>
      ) : (
        <Text type="secondary">未能获取到任务详情</Text>
      )}

      <ReportPreviewModal
        open={previewOpen}
        loading={previewLoading}
        report={previewReport}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewReport(null);
        }}
        onDownload={(r) => handleDownloadFile(r.filename, Boolean(r.is_html))}
      />

      <ResumeTaskModal
        open={resumeModalOpen}
        loading={resuming}
        onCancel={() => setResumeModalOpen(false)}
        onConfirm={handleConfirmResume}
      />
    </Drawer>
  );
};
