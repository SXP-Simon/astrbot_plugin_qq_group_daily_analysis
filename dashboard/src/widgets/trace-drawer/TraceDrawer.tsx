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
} from "antd";
import { ReloadOutlined, DatabaseOutlined, ClockCircleOutlined, SyncOutlined } from "@ant-design/icons";
import { fetchTraceDetail } from "../../entities/trace/api/traceApi";
import { TraceRecord } from "../../entities/trace/model/types";
import { StatusTag } from "../../shared/ui/StatusTag";
import { SpanTimeline } from "../../entities/trace/ui/SpanTimeline";
import { formatDuration, formatTokens, formatTimestamp, formatPercent, formatStageName } from "../../shared/lib/formatters";

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
  const [trace, setTrace] = useState<TraceRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDetail = (forceRefresh = false) => {
    if (!traceId) return;
    setLoading(true);
    fetchTraceDetail(traceId, forceRefresh)
      .then((data) => setTrace(data))
      .catch(() => setTrace(null))
      .finally(() => setLoading(false));
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
                                background: "rgba(0,0,0,0.04)",
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
            labelStyle={{ width: 85, color: "#595959", fontSize: 12 }}
            contentStyle={{ color: "#262626", fontSize: 12 }}
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
              <Tag style={{ margin: 0 }}>{trace.trigger_type === "manual" ? "手动触发" : trace.trigger_type === "auto" ? "定时触发" : trace.trigger_type}</Tag>
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
              labelStyle={{ width: 100, color: "#595959", fontSize: 12 }}
              contentStyle={{ color: "#262626", fontSize: 12 }}
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
              各阶段耗时明细
            </div>
            <SpanTimeline
              spans={trace.spans || []}
              totalDurationMs={totalDuration}
            />
          </div>
        </Space>
      ) : (
        <Text type="secondary">未能获取到任务详情</Text>
      )}
    </Drawer>
  );
};
