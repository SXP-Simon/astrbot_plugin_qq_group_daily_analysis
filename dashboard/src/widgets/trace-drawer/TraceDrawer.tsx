import React, { useEffect, useRef, useState } from "react";
import {
  Drawer,
  Descriptions,
  Tag,
  Alert,
  Typography,
  Spin,
  Collapse,
  Space,
  Button,
  message,
  Tooltip,
  Modal,
  Select,
  Form,
  theme,
} from "antd";
import {
  ReloadOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  FileTextOutlined,
  FileImageOutlined,
  PictureOutlined,
  EyeOutlined,
  DownloadOutlined,
  CopyOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import {
  fetchTraceDetail,
  resumeTraceTask,
  fetchProviderList,
  LLMProviderItem,
} from "../../entities/trace/api/traceApi";
import { fetchTraceLogs } from "../../entities/log/api/logApi";
import { fetchReportContent } from "../../entities/report/api/reportApi";
import { ReportItem } from "../../entities/report/model/types";
import { ReportPreviewModal } from "../report-preview-modal/ReportPreviewModal";
import { TraceRecord } from "../../entities/trace/model/types";
import { PluginLogItem, TAG_STYLE_MAP } from "../../entities/log/model/types";
import { StatusTag } from "../../shared/ui/StatusTag";
import { TriggerTypeTag } from "../../shared/ui/TriggerTypeTag";
import { SpanTimeline } from "../../entities/trace/ui/SpanTimeline";
import { formatDuration, formatTokens, formatTimestamp, formatPercent, formatStageName } from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";
import { copyToClipboard } from "../../shared/lib/clipboard";

const { Text, Paragraph } = Typography;

interface TraceDrawerProps {
  traceId: string | null;
  open: boolean;
  onClose: () => void;
}

export const TraceDrawer: React.FC<TraceDrawerProps> = ({
  traceId,
  open,
  onClose,
}) => {
  const { isDark } = useTheme();
  const { token } = theme.useToken();
  const [trace, setTrace] = useState<TraceRecord | null>(null);
  const [logs, setLogs] = useState<PluginLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [providers, setProviders] = useState<LLMProviderItem[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("auto");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBoxRef = useRef<HTMLDivElement>(null);

  const handleOpenResumeModal = async () => {
    setResumeModalOpen(true);
    setSelectedProvider("auto");
    setLoadingProviders(true);
    try {
      const list = await fetchProviderList();
      setProviders(list);
    } catch {
      // Ignore background fetch error
    } finally {
      setLoadingProviders(false);
    }
  };

  const handleConfirmResume = async () => {
    if (!traceId) return;
    setResuming(true);
    try {
      await resumeTraceTask(
        traceId,
        selectedProvider !== "auto" ? selectedProvider : undefined
      );
      message.success("已成功触发断点续跑任务，正在恢复分析...");
      setResumeModalOpen(false);
      loadDetail(true);
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
        cleanupBlobUrl = URL.createObjectURL(blob);
        href = cleanupBlobUrl;
      }
      if (!href) {
        message.error("未找到文件下载地址");
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
      message.success(`已开始下载 ${filename}`);
    } catch {
      message.error("下载文件异常");
    }
  };

  const loadDetail = (forceRefresh = false) => {
    if (!traceId) return;
    setLoading(true);
    fetchTraceDetail(traceId, forceRefresh)
      .then((data) => setTrace(data))
      .catch(() => setTrace(null))
      .finally(() => setLoading(false));

    fetchTraceLogs(traceId)
      .then((data) => setLogs(data))
      .catch(() => setLogs([]));
  };

  const handleCopyLogs = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!logs || logs.length === 0) {
      message.info("暂无可复制的日志");
      return;
    }
    const fullText = logs.map((l) => l.raw).join("\n");
    const ok = await copyToClipboard(fullText);
    if (ok) {
      message.success(`已复制 ${logs.length} 条专属日志`);
    } else {
      message.error("复制失败，请手动选中文本后复制");
    }
  };

  // 支持在日志区域内按下 Ctrl+A / Cmd+A 时仅全选日志区域内容，避免全屏选中
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      if (logBoxRef.current) {
        const range = document.createRange();
        range.selectNodeContents(logBoxRef.current);
        const sel = window.getSelection();
        if (sel) {
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
    }
  };

  useEffect(() => {
    if (open && traceId) {
      loadDetail(true);
    } else {
      setTrace(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, traceId]);

  // 运行中任务自动轮询刷新（每 3 秒）
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (open && trace?.status === "running" && traceId) {
      pollRef.current = setInterval(() => {
        fetchTraceDetail(traceId, true)
          .then((data) => {
            setTrace(data);
            // 任务已结束，停止轮询
            if (data && data.status !== "running" && pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          })
          .catch(() => {});
      }, 3000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [open, trace?.status, traceId]);

  const totalDuration = trace?.duration_ms || 1;

  return (
    <Drawer
      title={
        <Space size="middle">
          <span style={{ fontSize: 16, fontWeight: 600 }}>任务执行详情</span>
          {trace && <StatusTag status={trace.status} />}
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
              onClick={handleOpenResumeModal}
            >
              幂等续跑
            </Button>
          )}
          <Button
            size="small"
            type="text"
            icon={<ReloadOutlined spin={loading} />}
            onClick={() => loadDetail(true)}
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
      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin tip="正在加载任务详情..." />
        </div>
      ) : trace ? (
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {/* 1a. 运行中状态提示 */}
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
                    （已自动每 3 秒刷新，任务结束后将显示完整数据）
                  </Text>
                </span>
              }
            />
          )}

          {/* 1b. 错误告警 */}
          {trace.status === "failed" && (
            <Alert
              type="error"
              showIcon
              message={trace.error_stage ? `在【${formatStageName(trace.error_stage)}】阶段发生异常` : "分析过程发生异常"}
              description={
                <div>
                  <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: "展开详情" }} style={{ marginBottom: 4 }}>
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
                      onClick={handleOpenResumeModal}
                    >
                      🔄 从 Checkpoint 幂等续跑此任务
                    </Button>
                  </div>
                  {trace.stack_trace && (
                    <Collapse
                      size="small"
                      ghost
                      items={[
                        {
                          key: "stack",
                          label: "详细错误调用栈",
                          children: (
                            <pre
                              style={{
                                fontSize: 11,
                                fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
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

          {/* 2. 基本信息 */}
          <Descriptions
            size="small"
            bordered
            column={2}
            labelStyle={{ width: 85, fontSize: 12 }}
            contentStyle={{ fontSize: 12 }}
          >
            <Descriptions.Item label="任务编号" span={2}>
              <Text copyable style={{ fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace', fontSize: 12 }}>
                {trace.trace_id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="分析群聊" span={2}>
              <span>
                {trace.group_name || "未知群"} <Text type="secondary">({trace.group_id})</Text>
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="接入平台">
              <Tag style={{ margin: 0 }}>
                {!trace.platform || trace.platform === "auto" || trace.platform === "default"
                  ? "-"
                  : trace.platform}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="触发方式">
              <TriggerTypeTag triggerType={trace.trigger_type} />
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              <span>{formatTimestamp(trace.started_at)}</span>
            </Descriptions.Item>
            <Descriptions.Item label="执行总耗时">
              <span style={{ color: "#1677ff", fontWeight: 600 }}>
                {formatDuration(trace.duration_ms)}
              </span>
            </Descriptions.Item>
          </Descriptions>

          {/* 3. 上下文演进与 Token */}
          {(trace.context_metrics || trace.token_usage) && (
            <Descriptions
              title={
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <DatabaseOutlined style={{ marginRight: 6, color: "#1677ff" }} />
                  消息处理与模型消耗
                </span>
              }
              size="small"
              bordered
              column={2}
              labelStyle={{ width: 100, fontSize: 12 }}
              contentStyle={{ fontSize: 12 }}
            >
              {trace.context_metrics && (
                <>
                  <Descriptions.Item label="读取原始消息">
                    <span>{trace.context_metrics.raw_message_count.toLocaleString()} 条</span>
                  </Descriptions.Item>
                  <Descriptions.Item label="有效消息留存">
                    <span style={{ color: "#52c41a", fontWeight: 500 }}>
                      {trace.context_metrics.cleaned_message_count.toLocaleString()} 条 ({formatPercent(trace.context_metrics.compression_ratio)})
                    </span>
                  </Descriptions.Item>
                </>
              )}
              {trace.token_usage && (
                <>
                  <Descriptions.Item label="模型消耗总量">
                    <span style={{ fontWeight: 600 }}>
                      {formatTokens(trace.token_usage.total_tokens)}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="输入 / 输出">
                    <span style={{ fontSize: 11 }}>
                      输入: {formatTokens(trace.token_usage.prompt_tokens)} / 输出: {formatTokens(trace.token_usage.completion_tokens)}
                    </span>
                  </Descriptions.Item>
                </>
              )}
            </Descriptions>
          )}

          {/* 4. 产物报告文件 */}
          {(() => {
            const rawFiles =
              trace.report_files ||
              (Array.isArray(trace.extra?.report_files)
                ? (trace.extra.report_files as TraceRecord["report_files"])
                : []) ||
              [];
            const seenNames = new Set<string>();
            const reportFiles = rawFiles.filter((f) => {
              if (!f || !f.filename || seenNames.has(f.filename)) return false;
              seenNames.add(f.filename);
              return true;
            });
            if (!reportFiles || reportFiles.length === 0) return null;
            return (
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  <FileImageOutlined style={{ marginRight: 6, color: "#52c41a" }} />
                  产物报告文件 ({reportFiles.length} 个)
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {reportFiles.map((file, idx) => {
                    const isHtml = Boolean(
                      file.format === "html" ||
                        file.filename.toLowerCase().endsWith(".html") ||
                        file.filename.toLowerCase().endsWith(".htm")
                    );
                    const isComic = Boolean(
                      file.report_type === "comic" ||
                        file.filename.toLowerCase().startsWith("comic_") ||
                        file.filename.startsWith("漫画_")
                    );
                    return (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "8px 12px",
                          background: isDark ? "rgba(255,255,255,0.03)" : "#f8fafc",
                          border: `1px solid ${isDark ? "rgba(255,255,255,0.08)" : "#e2e8f0"}`,
                          borderRadius: 4,
                          gap: 8,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            minWidth: 0,
                            flex: 1,
                            gap: 6,
                            overflow: "hidden",
                          }}
                        >
                          {isComic ? (
                            <PictureOutlined
                              style={{ color: "#eb2f96", flexShrink: 0 }}
                            />
                          ) : isHtml ? (
                            <FileTextOutlined
                              style={{ color: "#fa8c16", flexShrink: 0 }}
                            />
                          ) : (
                            <FileImageOutlined
                              style={{ color: "#1677ff", flexShrink: 0 }}
                            />
                          )}
                          <Tooltip title={file.filename} placement="topLeft">
                            <span
                              style={{
                                fontSize: 12,
                                fontWeight: 600,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                minWidth: 0,
                              }}
                            >
                              {file.filename}
                            </span>
                          </Tooltip>
                          <Tag
                            color={isComic ? "magenta" : isHtml ? "orange" : "blue"}
                            style={{
                              margin: 0,
                              fontSize: 10,
                              lineHeight: "16px",
                              flexShrink: 0,
                            }}
                          >
                            {isComic ? "群漫画" : isHtml ? "HTML" : "日报长图"}
                          </Tag>
                          {file.size_bytes ? (
                            <Text
                              type="secondary"
                              style={{
                                fontSize: 11,
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                              }}
                            >
                              ({(file.size_bytes / 1024).toFixed(1)} KB)
                            </Text>
                          ) : null}
                        </div>
                        <Space size="small" style={{ flexShrink: 0, whiteSpace: "nowrap" }}>
                          <Button
                            size="small"
                            type="primary"
                            ghost
                            icon={<EyeOutlined />}
                            onClick={() => handlePreviewFile(file.filename, isHtml)}
                            style={{ fontSize: 11, height: 24 }}
                          >
                            {isComic ? "预览漫画" : isHtml ? "预览 HTML" : "预览大图"}
                          </Button>
                          <Button
                            size="small"
                            icon={<DownloadOutlined />}
                            onClick={() => handleDownloadFile(file.filename, isHtml)}
                            style={{ fontSize: 11, height: 24 }}
                          >
                            下载
                          </Button>
                        </Space>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}

          {/* 5. 阶段耗时甘特瀑布流 */}
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              <ClockCircleOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
              各阶段耗时明细与展开诊断
            </div>
            <SpanTimeline
              spans={trace.spans || []}
              totalDurationMs={totalDuration}
            />
          </div>

          {/* 6. 专属执行日志流 */}
          {logs && logs.length > 0 && (
            <Collapse
              size="small"
              items={[
                {
                  key: "trace-logs",
                  label: (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                      <span style={{ fontSize: 12, fontWeight: 600 }}>
                        <FileTextOutlined style={{ marginRight: 6, color: "#1677ff" }} />
                        专属执行日志 ({logs.length} 条)
                      </span>
                      <Tooltip title="一键复制当前任务专属日志">
                        <Button
                          size="small"
                          type="text"
                          icon={<CopyOutlined />}
                          onClick={handleCopyLogs}
                          style={{ fontSize: 11, height: 22, padding: "0 6px" }}
                        >
                          复制日志
                        </Button>
                      </Tooltip>
                    </div>
                  ),
                  children: (
                    <div
                      ref={logBoxRef}
                      tabIndex={0}
                      onKeyDown={handleKeyDown}
                      style={{
                        background: isDark ? "#0d1117" : "#f8fafc",
                        color: isDark ? "#e6edf3" : "#1e293b",
                        borderRadius: 4,
                        padding: "8px 10px",
                        fontFamily:
                          'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                        fontSize: 11,
                        maxHeight: 240,
                        overflowY: "auto",
                        border: `1px solid ${isDark ? "#303030" : "#e2e8f0"}`,
                        outline: "none",
                      }}
                    >
                      {logs.map((l) => {
                        const isError = l.level === "ERROR" || l.level === "CRITICAL";
                        const isWarn = l.level === "WARNING";
                        const tagColor = TAG_STYLE_MAP[l.tag]?.color || "default";

                        return (
                          <div
                            key={l.id}
                            style={{
                              padding: "2px 0",
                              borderBottom: `1px solid ${isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)"}`,
                              color: isError
                                ? isDark ? "#ff7875" : "#cf1322"
                                : isWarn
                                ? isDark ? "#ffc069" : "#d46b08"
                                : isDark ? "#d9d9d9" : "#1e293b",
                            }}
                          >
                            <span style={{ color: isDark ? "#8b949e" : "#64748b", marginRight: 6 }}>
                              {l.time_str.split(" ")[1]}
                            </span>
                            <span style={{ marginRight: 6, fontWeight: 600 }}>
                              [{l.level}]
                            </span>
                            {l.tag && (
                              <Tag
                                color={tagColor}
                                style={{
                                  margin: "0 6px 0 0",
                                  fontSize: 10,
                                  padding: "0 3px",
                                  lineHeight: "16px",
                                }}
                              >
                                {l.tag}
                              </Tag>
                            )}
                            <span>{l.message}</span>
                          </div>
                        );
                      })}
                    </div>
                  ),
                },
              ]}
            />
          )}
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

      <Modal
        title={
          <Space>
            <SyncOutlined />
            <span>幂等断点续跑 / 重试分析</span>
          </Space>
        }
        open={resumeModalOpen}
        onCancel={() => setResumeModalOpen(false)}
        onOk={handleConfirmResume}
        confirmLoading={resuming}
        okText="立即续跑"
        cancelText="取消"
        destroyOnClose
        width={460}
      >
        <div style={{ marginTop: 12 }}>
          <Alert
            type="info"
            showIcon
            message="零浪费 Token 细粒度产物复用"
            description="系统已自动跳过消息拉取与清洗，并直接复用本次任务中已有非空产物的子分析（如已生成的话题/画像），仅对失败或未完成的子任务向大模型发起补充请求。"
            style={{ marginBottom: 16 }}
          />

          <Form layout="vertical">
            <Form.Item
              label={
                <Space>
                  <ApiOutlined />
                  <span>指定大模型 Provider (选填)</span>
                </Space>
              }
              extra="若上次分析因大模型崩溃、限流或 Provider 故障中断，可在此临时指定其他备用模型完成续跑"
            >
              <Select
                value={selectedProvider}
                onChange={setSelectedProvider}
                loading={loadingProviders}
                options={[
                  { label: "跟随系统默认配置 (推荐)", value: "auto" },
                  ...providers.map((p) => ({
                    label: p.label || `${p.name} (${p.id})`,
                    value: p.id,
                  })),
                ]}
              />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </Drawer>
  );
};
