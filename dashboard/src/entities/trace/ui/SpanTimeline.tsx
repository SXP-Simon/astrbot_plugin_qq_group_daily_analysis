import React, { useState } from "react";
import { Timeline, Tag, Typography, Progress, Space, Tooltip, theme } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { TraceSpan } from "../model/types";
import { formatDuration, formatStageName } from "../../../shared/lib/formatters";

const { Text } = Typography;

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
}

/**
 * 依据各阶段特性（本地计算 vs 外部协议 vs 大模型 vs 绘图）制定 SLA 健康基线与超时预算
 */
function getStageSlaThreshold(stageName: string): { thresholdMs: number; description: string } {
  const norm = (stageName || "").toUpperCase();
  if (
    norm.includes("LLM") ||
    norm.includes("话题") ||
    norm.includes("画像") ||
    norm.includes("金句")
  ) {
    return { thresholdMs: 120000, description: "大模型多轮分析健康阈值 120s" };
  }
  if (
    norm.includes("COMIC") ||
    norm.includes("漫画") ||
    norm.includes("DRAW") ||
    norm.includes("T2I")
  ) {
    return { thresholdMs: 180000, description: "文生图/绘图排队健康阈值 180s" };
  }
  if (
    norm.includes("RENDER") ||
    norm.includes("渲染") ||
    norm.includes("REPORT")
  ) {
    return { thresholdMs: 45000, description: "长图渲染与平台发送健康阈值 45s" };
  }
  if (norm.includes("FETCH") || norm.includes("拉取")) {
    return { thresholdMs: 20000, description: "平台消息抓取健康阈值 20s" };
  }
  if (
    norm.includes("CLEAN") ||
    norm.includes("清洗") ||
    norm.includes("STATS") ||
    norm.includes("统计") ||
    norm.includes("SAVE") ||
    norm.includes("持久化")
  ) {
    return { thresholdMs: 5000, description: "本地计算/SQLite 处理健康阈值 5s" };
  }
  return { thresholdMs: 30000, description: "常规流程健康阈值 30s" };
}

export const SpanTimeline: React.FC<SpanTimelineProps> = ({
  spans,
  totalDurationMs = 1,
}) => {
  const { token } = theme.useToken();
  const [expandedSpanIds, setExpandedSpanIds] = useState<string[]>([]);

  if (!spans || spans.length === 0) {
    return <Text type="secondary">无执行阶段记录</Text>;
  }

  const toggleExpand = (id: string) => {
    setExpandedSpanIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const items = spans.map((span, idx) => {
    const spanKey = span.span_id || `span_${idx}_${span.stage_name}`;
    const duration = span.duration_ms || 0;
    const durationPct = Math.min(
      100,
      Math.max(2, Math.round((duration / Math.max(1, totalDurationMs)) * 100))
    );

    const { thresholdMs, description: slaDesc } = getStageSlaThreshold(span.stage_name);
    const isSlaExceeded = duration > thresholdMs;
    const isFailed = span.status === "failed" || span.status === "error";
    const isRunning = span.status === "running";

    let color = "#52c41a";
    let icon = <CheckCircleOutlined style={{ color: "#52c41a" }} />;
    let tagColor = "success";

    if (isFailed) {
      color = "#ff4d4f";
      icon = <CloseCircleOutlined style={{ color: "#ff4d4f" }} />;
      tagColor = "error";
    } else if (isRunning) {
      color = "#1677ff";
      icon = <SyncOutlined spin style={{ color: "#1677ff" }} />;
      tagColor = "processing";
    } else if (isSlaExceeded) {
      color = "#fa8c16";
      icon = <CheckCircleOutlined style={{ color: "#fa8c16" }} />;
      tagColor = "warning";
    }

    const isExpanded = expandedSpanIds.includes(spanKey);
    const hasPayload = span.payload && Object.keys(span.payload).length > 0;

    return {
      dot: icon,
      children: (
        <div
          style={{
            marginBottom: 12,
            background: isExpanded ? token.colorFillAlter : "transparent",
            borderRadius: 6,
            padding: isExpanded ? "8px 10px" : "0",
            transition: "all 0.2s ease",
          }}
        >
          {/* 阶段标题与耗时条 */}
          <div
            onClick={() => toggleExpand(spanKey)}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <Space size={6}>
              {isExpanded ? (
                <DownOutlined style={{ fontSize: 10, color: token.colorTextTertiary }} />
              ) : (
                <RightOutlined style={{ fontSize: 10, color: token.colorTextTertiary }} />
              )}
              <span style={{ fontWeight: 600, fontSize: 13, color: token.colorText }}>
                {formatStageName(span.stage_name)}
              </span>
              {isSlaExceeded && (
                <Tooltip title={`该阶段耗时已超出预期的健康基线 (${slaDesc})`}>
                  <Tag
                    color="warning"
                    icon={<WarningOutlined />}
                    style={{ margin: 0, fontSize: 10, padding: "0 4px", lineHeight: "18px" }}
                  >
                    耗时超出健康基线
                  </Tag>
                </Tooltip>
              )}
            </Space>

            <Space size={6}>
              <span style={{ fontSize: 11, color: token.colorTextSecondary }}>
                占 {durationPct}%
              </span>
              <Tag
                color={tagColor}
                style={{
                  fontSize: 11,
                  borderRadius: 4,
                  margin: 0,
                  fontWeight: 600,
                }}
              >
                {formatDuration(span.duration_ms)}
              </Tag>
            </Space>
          </div>

          <Progress
            percent={durationPct}
            size="small"
            showInfo={false}
            strokeColor={color}
            style={{ margin: "4px 0 2px 0" }}
          />

          {/* 展开的阶段参数与日志详情 */}
          {isExpanded && (
            <div style={{ marginTop: 8 }}>
              {isFailed && (
                <div
                  style={{
                    padding: "6px 8px",
                    background: token.colorErrorBg,
                    border: `1px solid ${token.colorErrorBorder}`,
                    borderRadius: 4,
                    color: token.colorErrorText,
                    fontSize: 12,
                    marginBottom: 6,
                  }}
                >
                  <Text type="danger" strong>
                    阶段异常：
                  </Text>
                  <span>{String(span.payload?.error || "该流程执行异常中断")}</span>
                </div>
              )}

              {Array.isArray(span.payload?.subtask_errors) &&
                span.payload.subtask_errors.length > 0 && (
                  <div
                    style={{
                      padding: "6px 8px",
                      background: token.colorWarningBg,
                      border: `1px solid ${token.colorWarningBorder}`,
                      borderRadius: 4,
                      color: token.colorWarningText,
                      fontSize: 12,
                      marginBottom: 6,
                    }}
                  >
                    <Text style={{ color: "#d46b08" }} strong>
                      部分子任务调用异常：
                    </Text>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {span.payload.subtask_errors.map((err: string, i: number) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

              {hasPayload ? (
                <div>
                  <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 4 }}>
                    阶段调用参数与执行产物明细：
                  </div>
                  <pre
                    style={{
                      fontSize: 11,
                      fontFamily:
                        'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                      background: token.colorFillAlter,
                      color: token.colorText,
                      border: `1px solid ${token.colorBorderSecondary}`,
                      padding: "6px 8px",
                      borderRadius: 4,
                      margin: 0,
                      maxHeight: 140,
                      overflowY: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                    }}
                  >
                    {JSON.stringify(span.payload, null, 2)}
                  </pre>
                </div>
              ) : (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  阶段执行正常，无额外上下文字段
                </Text>
              )}
            </div>
          )}
        </div>
      ),
    };
  });

  return <Timeline items={items} style={{ marginTop: 12 }} />;
};

