import React, { useState } from "react";
import {
  Timeline,
  Tag,
  Typography,
  Progress,
  Space,
  Tooltip,
  theme,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { TraceSpan } from "../model/types";
import { getStageSlaThreshold } from "../model/sla";
import { formatDuration, formatStageName } from "../../../shared/lib/formatters";
import { StageMetricsBadges } from "./StageMetricsBadges";
import { PromptsInspector, PromptDetail } from "./PromptsInspector";
import { SpanPayloadViewer } from "./SpanPayloadViewer";

const { Text } = Typography;

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
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
              {/* 异常提示 */}
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

              {/* 子任务错误提示 */}
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

              {/* LLM 分析未产出提示 */}
              {span.stage_name === "LLM_ANALYSIS" &&
                span.payload?.topics_count === 0 &&
                (!span.payload?.prompt_tokens || span.payload?.prompt_tokens === 0) &&
                (!Array.isArray(span.payload?.subtask_errors) ||
                  span.payload?.subtask_errors.length === 0) && (
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
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "ℹ️ 本次任务已在配置中关闭所有大模型文本分析模块"
                        : "⚠️ 大模型分析未产出有效内容："}
                    </Text>
                    <div style={{ marginTop: 2 }}>
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "配置项中话题、群友画像、金句和质量锐评均未开启。"
                        : "模型未消耗 Token 或未能解析出任何话题/画像/金句，请检查大模型 Provider 连接与配置。"}
                    </div>
                  </div>
                )}

              {/* 各生命周期阶段专属标签 */}
              <StageMetricsBadges
                stageName={span.stage_name}
                payload={span.payload as Record<string, unknown> | undefined}
              />

              {/* LLM 真实提示词 Prompt 检视器 */}
              {span.stage_name === "LLM_ANALYSIS" && (
                <PromptsInspector
                  prompts={
                    span.payload?.prompts as Record<string, PromptDetail | string> | undefined
                  }
                />
              )}

              {/* 通用调用产物明细 */}
              <SpanPayloadViewer
                payload={span.payload as Record<string, unknown> | undefined}
              />
            </div>
          )}
        </div>
      ),
    };
  });

  return (
    <Timeline
      mode="left"
      items={items}
      style={{ marginTop: 8, paddingLeft: 4 }}
    />
  );
};
