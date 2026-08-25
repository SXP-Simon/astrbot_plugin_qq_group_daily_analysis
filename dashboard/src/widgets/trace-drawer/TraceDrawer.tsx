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
} from "antd";
import {
  ReloadOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  FileTextOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import { fetchTraceDetail } from "../../entities/trace/api/traceApi";
import { fetchTraceLogs } from "../../entities/log/api/logApi";
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
  const [trace, setTrace] = useState<TraceRecord | null>(null);
  const [logs, setLogs] = useState<PluginLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBoxRef = useRef<HTMLDivElement>(null);

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
        <Button
          size="small"
          type="text"
          icon={<ReloadOutlined spin={loading} />}
          onClick={() => loadDetail(true)}
        >
          刷新
        </Button>
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
                                background: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)",
                                color: isDark ? "#e6edf3" : "#262626",
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
            labelStyle={{ width: 85, color: isDark ? "#8c8c8c" : "#595959", fontSize: 12 }}
            contentStyle={{ color: isDark ? "#e6edf3" : "#262626", fontSize: 12 }}
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
              <Tag style={{ margin: 0 }}>{trace.platform || "qq"}</Tag>
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
              labelStyle={{ width: 100, color: isDark ? "#8c8c8c" : "#595959", fontSize: 12 }}
              contentStyle={{ color: isDark ? "#e6edf3" : "#262626", fontSize: 12 }}
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

          {/* 4. 阶段耗时甘特瀑布流 */}
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

          {/* 5. 专属执行日志流 */}
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
    </Drawer>
  );
};
