import React, { useState } from "react";
import { Timeline, Typography, Space, theme } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { TraceSpan } from "../model/types";
import { getStageSlaThreshold } from "../model/sla";
import { StageMetricsBadges } from "./StageMetricsBadges";
import { PromptsInspector, PromptDetail } from "./PromptsInspector";
import { SpanPayloadViewer } from "./SpanPayloadViewer";
import { SpanHeader } from "./SpanHeader";
import { SpanAlerts } from "./SpanAlerts";
import { LlmAttemptsTable } from "./LlmAttemptsTable";
import { RenderAttemptsTable } from "./RenderAttemptsTable";

const { Text } = Typography;

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
  currentStage?: string;
  taskStatus?: string;
}

export const SpanTimeline: React.FC<SpanTimelineProps> = ({
  spans,
  totalDurationMs = 1,
  currentStage,
  taskStatus,
}) => {
  const { token } = theme.useToken();
  const [expandedSpanIds, setExpandedSpanIds] = useState<string[]>([]);
  const [, setTick] = useState(0);

  // 运行中状态下每秒自动步进，驱动运行中阶段的实时计时器和动画
  React.useEffect(() => {
    if (taskStatus === "running") {
      const timer = setInterval(() => setTick((t) => t + 1), 1000);
      return () => clearInterval(timer);
    }
  }, [taskStatus]);

  const mergedSpans = React.useMemo(() => {
    const list = [...(spans || [])];
    if (taskStatus === "running" && currentStage) {
      const hasActive = list.some(
        (s) => s.status === "running" || s.stage_name === currentStage
      );
      if (!hasActive) {
        list.push({
          span_id: `active_${currentStage}`,
          trace_id: "",
          stage_name: currentStage,
          status: "running",
          started_at: Date.now() / 1000 - 1,
          duration_ms: null,
          payload: {
            note: "当前阶段正在异步处理中...",
          },
        });
      }
    }
    return list;
  }, [spans, taskStatus, currentStage]);

  if (!mergedSpans || mergedSpans.length === 0) {
    if (taskStatus === "running") {
      return (
        <div style={{ padding: "8px 0" }}>
          <Space>
            <SyncOutlined spin style={{ color: "#1677ff" }} />
            <Text type="secondary">正在初始化执行生命周期阶段...</Text>
          </Space>
        </div>
      );
    }
    return <Text type="secondary">无执行阶段记录</Text>;
  }

  const toggleExpand = (id: string) => {
    setExpandedSpanIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const items = mergedSpans.map((span, idx) => {
    const spanKey = span.span_id || `span_${idx}_${span.stage_name}`;
    const isRunning = span.status === "running";
    const duration =
      span.duration_ms !== null && span.duration_ms !== undefined
        ? span.duration_ms
        : Math.max(0, Math.round((Date.now() / 1000 - (span.started_at || Date.now() / 1000)) * 1000));

    const { thresholdMs } = getStageSlaThreshold(span.stage_name);
    const isSlaExceeded = !isRunning && duration > thresholdMs;
    const isFailed =
      span.status === "failed" ||
      span.status === "error" ||
      Boolean(span.payload?.error);

    const isWarning =
      !isFailed &&
      (span.status === "warning" ||
        span.status === "partial_success" ||
        Boolean(span.payload?.warning) ||
        (Array.isArray(span.payload?.subtask_errors) && span.payload.subtask_errors.length > 0));

    let icon = <CheckCircleOutlined style={{ color: "#52c41a" }} />;
    if (isFailed) {
      icon = <CloseCircleOutlined style={{ color: "#ff4d4f" }} />;
    } else if (isRunning) {
      icon = <SyncOutlined spin style={{ color: "#1677ff" }} />;
    } else if (isWarning) {
      icon = <ExclamationCircleOutlined style={{ color: "#fa8c16" }} />;
    } else if (isSlaExceeded) {
      icon = <CheckCircleOutlined style={{ color: "#fa8c16" }} />;
    }

    const isExpanded = expandedSpanIds.includes(spanKey);
    const llmAttempts = Array.isArray(span.payload?.llm_attempts)
      ? (span.payload.llm_attempts as Array<Record<string, unknown>>)
      : [];
    const renderAttempts = Array.isArray(span.payload?.render_attempts)
      ? (span.payload.render_attempts as Array<Record<string, unknown>>)
      : [];

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
          <SpanHeader
            stageName={span.stage_name}
            durationMs={span.duration_ms}
            startedAt={span.started_at}
            totalDurationMs={totalDurationMs}
            status={span.status}
            isExpanded={isExpanded}
            onToggleExpand={() => toggleExpand(spanKey)}
            payload={span.payload as Record<string, unknown> | undefined}
          />

          {/* 展开的阶段参数与日志详情 */}
          {isExpanded && (
            <div style={{ marginTop: 8 }}>
              {/* 异常与警告提示 */}
              <SpanAlerts
                stageName={span.stage_name}
                status={span.status}
                payload={span.payload as Record<string, unknown> | undefined}
              />

              {/* 各生命周期阶段专属数据标签 */}
              <StageMetricsBadges
                stageName={span.stage_name}
                payload={span.payload as Record<string, unknown> | undefined}
              />

              {/* LLM 调用与重试链路表格 */}
              <LlmAttemptsTable attempts={llmAttempts} />

              {/* 渲染策略与降级表格 */}
              <RenderAttemptsTable attempts={renderAttempts} />

              {/* LLM 真实提示词 Prompt 检视器 */}
              {(span.stage_name === "LLM_ANALYSIS" || Boolean(span.payload?.prompts)) && (
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
