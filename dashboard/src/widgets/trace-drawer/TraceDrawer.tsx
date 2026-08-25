import React, { useEffect, useState } from "react";
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
import { ReloadOutlined, DatabaseOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { fetchTraceDetail } from "../../entities/trace/api/traceApi";
import { TraceRecord } from "../../entities/trace/model/types";
import { StatusTag } from "../../shared/ui/StatusTag";
import { SpanTimeline } from "../../entities/trace/ui/SpanTimeline";
import { formatDuration, formatTokens, formatTimestamp, formatPercent } from "../../shared/lib/formatters";

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
      loadDetail(false);
    } else {
      setTrace(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, traceId]);

  const totalDuration = trace?.duration_ms || 1;

  return (
    <Drawer
      title={
        <Space>
          <span>任务详情</span>
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
      width={640}
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
          {/* 1. 错误告警 */}
          {trace.status === "failed" && (
            <Alert
              type="error"
              showIcon
              message={trace.error_stage ? `在【${trace.error_stage}】阶段发生异常` : "分析过程发生异常"}
              description={
                <div>
                  <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: "展开详情" }}>
                    {trace.error_message || "未知错误"}
                  </Paragraph>
                  {trace.stack_trace && (
                    <Collapse
                      size="small"
                      ghost
                      items={[
                        {
                          key: "stack",
                          label: "详细错误日志",
                          children: (
                            <pre
                              className="font-mono"
                              style={{
                                fontSize: 11,
                                background: "rgba(0,0,0,0.03)",
                                padding: 8,
                                borderRadius: 4,
                                maxHeight: 200,
                                overflow: "auto",
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
          <Descriptions size="small" bordered column={{ xs: 1, sm: 2 }}>
            <Descriptions.Item label="任务编号">
              <Text copyable className="font-mono">{trace.trace_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="群聊">
              <span className="font-mono">
                {trace.group_name || "未知群"} ({trace.group_id})
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="平台">
              <Tag>{trace.platform || "qq"}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="触发方式">
              <Tag>{trace.trigger_type === "manual" ? "手动触发" : trace.trigger_type === "auto" ? "定时触发" : trace.trigger_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              <span className="font-mono">
                {formatTimestamp(trace.started_at)}
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="总耗时">
              <span className="font-mono font-semibold" style={{ color: "#1677ff" }}>
                {formatDuration(trace.duration_ms)}
              </span>
            </Descriptions.Item>
          </Descriptions>

          {/* 3. 上下文演进与 Token */}
          {(trace.context_metrics || trace.token_usage) && (
            <Descriptions
              title={
                <span style={{ fontSize: 13 }}>
                  <DatabaseOutlined style={{ marginRight: 6, color: "#1677ff" }} />
                  消息处理与模型消耗
                </span>
              }
              size="small"
              bordered
              column={{ xs: 1, sm: 2 }}
            >
              {trace.context_metrics && (
                <>
                  <Descriptions.Item label="读取消息数">
                    <span className="font-mono">{trace.context_metrics.raw_message_count} 条</span>
                  </Descriptions.Item>
                  <Descriptions.Item label="有效消息保留">
                    <span className="font-mono">
                      {trace.context_metrics.cleaned_message_count} 条 (
                      {formatPercent(trace.context_metrics.compression_ratio)})
                    </span>
                  </Descriptions.Item>
                </>
              )}
              {trace.token_usage && (
                <>
                  <Descriptions.Item label="模型消耗总量">
                    <span className="font-mono font-semibold">
                      {formatTokens(trace.token_usage.total_tokens)}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="输入 / 输出消耗">
                    <span className="font-mono text-xs">
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
