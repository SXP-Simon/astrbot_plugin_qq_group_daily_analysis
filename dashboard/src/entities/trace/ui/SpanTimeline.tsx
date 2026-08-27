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
  ExclamationCircleOutlined,
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
  const isDark = Boolean(token.colorBgBase && token.colorBgBase.toLowerCase().includes("#1"));
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
        : Math.max(
            0,
            Math.round(
              (Date.now() / 1000 - (span.started_at || Date.now() / 1000)) * 1000
            )
          );
    const durationPct = isRunning
      ? 100
      : Math.min(
          100,
          Math.max(2, Math.round((duration / Math.max(1, totalDurationMs)) * 100))
        );

    const { thresholdMs, description: slaDesc } = getStageSlaThreshold(span.stage_name);
    const isSlaExceeded = !isRunning && duration > thresholdMs;
    const isFailed = span.status === "failed" || span.status === "error";
    const isWarning =
      !isFailed &&
      (span.status === "warning" ||
        span.status === "partial_success" ||
        Boolean(span.payload?.warning) ||
        (Array.isArray(span.payload?.subtask_errors) && span.payload.subtask_errors.length > 0));

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
    } else if (isWarning) {
      color = "#fa8c16";
      icon = <ExclamationCircleOutlined style={{ color: "#fa8c16" }} />;
      tagColor = "warning";
    } else if (isSlaExceeded) {
      color = "#fa8c16";
      icon = <CheckCircleOutlined style={{ color: "#fa8c16" }} />;
      tagColor = "warning";
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
              {!isRunning && (
                <span style={{ fontSize: 11, color: token.colorTextSecondary }}>
                  占 {durationPct}%
                </span>
              )}
              <Tag
                color={tagColor}
                icon={isRunning ? <SyncOutlined spin /> : undefined}
                style={{
                  fontSize: 11,
                  borderRadius: 4,
                  margin: 0,
                  fontWeight: 600,
                }}
              >
                {isRunning
                  ? `执行中 (${formatDuration(duration)})`
                  : isWarning
                  ? `告警 (${formatDuration(span.duration_ms ?? 0)})`
                  : isFailed
                  ? `失败 (${formatDuration(span.duration_ms ?? 0)})`
                  : formatDuration(span.duration_ms ?? 0)}
              </Tag>
            </Space>
          </div>

          <Progress
            percent={isRunning ? 100 : durationPct}
            status={isRunning ? "active" : "normal"}
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
                    padding: "6px 10px",
                    background: isDark ? "rgba(220, 38, 38, 0.1)" : "#fef2f2",
                    borderLeft: "3px solid #ef4444",
                    borderRadius: "0 4px 4px 0",
                    color: isDark ? "#fca5a5" : "#b91c1c",
                    fontSize: 11,
                    marginBottom: 8,
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ fontWeight: 600, marginRight: 6 }}>阶段执行异常：</span>
                  <span className="font-mono">{String(span.payload?.error || "该流程执行异常中断")}</span>
                </div>
              )}

              {/* 子任务错误提示 */}
              {Array.isArray(span.payload?.subtask_errors) &&
                span.payload.subtask_errors.length > 0 && (
                  <div
                    style={{
                      padding: "6px 10px",
                      background: isDark ? "rgba(217, 119, 6, 0.1)" : "#fffbeb",
                      borderLeft: "3px solid #f59e0b",
                      borderRadius: "0 4px 4px 0",
                      color: isDark ? "#fbbf24" : "#92400e",
                      fontSize: 11,
                      marginBottom: 8,
                      lineHeight: 1.5,
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>
                      部分子任务调用异常：
                    </div>
                    {span.payload.subtask_errors.map((err: string, i: number) => (
                      <div key={i} className="font-mono" style={{ fontSize: 10, marginTop: 1 }}>
                        • {err}
                      </div>
                    ))}
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
                      padding: "6px 10px",
                      background: isDark ? "rgba(217, 119, 6, 0.1)" : "#fffbeb",
                      borderLeft: "3px solid #f59e0b",
                      borderRadius: "0 4px 4px 0",
                      color: isDark ? "#fbbf24" : "#92400e",
                      fontSize: 11,
                      marginBottom: 8,
                      lineHeight: 1.5,
                    }}
                  >
                    <span style={{ fontWeight: 600, marginRight: 6 }}>
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "提示："
                        : "警告："}
                    </span>
                    <span>
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "配置项中话题、群友画像、金句和质量锐评均未开启。"
                        : "模型未消耗 Token 或未能解析出任何话题/画像/金句，请检查大模型 Provider 连接与配置。"}
                    </span>
                  </div>
                )}

              {/* 各生命周期阶段专属数据标签 */}
              <StageMetricsBadges
                stageName={span.stage_name}
                payload={span.payload as Record<string, unknown> | undefined}
              />

              {/* LLM 调用与重试链路紧凑表格 */}
              {llmAttempts.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    marginBottom: 8,
                    border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                    borderRadius: 4,
                    overflow: "hidden",
                    background: isDark ? "#161b22" : "#ffffff",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "5px 8px",
                      background: isDark ? "#21262d" : "#f8fafc",
                      borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                      fontSize: 11,
                    }}
                  >
                    <span style={{ fontWeight: 600, color: isDark ? "#c9d1d9" : "#334155" }}>
                      大模型调用与重试链路
                    </span>
                    <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
                      共 {llmAttempts.length} 次请求
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column" }}>
                    {llmAttempts.map((att: Record<string, unknown>, i: number) => {
                      const isSuccess = att.status === "success";
                      const isFallback = Boolean(att.is_fallback);
                      const hasError = !isSuccess && Boolean(att.error);

                      return (
                        <div
                          key={i}
                          style={{
                            padding: "6px 8px",
                            borderBottom:
                              i < llmAttempts.length - 1
                                ? `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`
                                : "none",
                            fontSize: 11,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 6,
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                              <span
                                className="font-mono"
                                style={{
                                  fontSize: 10,
                                  padding: "1px 5px",
                                  borderRadius: 3,
                                  background: isFallback
                                    ? (isDark ? "rgba(217, 119, 6, 0.15)" : "#fef3c7")
                                    : (isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff"),
                                  color: isFallback
                                    ? (isDark ? "#fbbf24" : "#b45309")
                                    : (isDark ? "#60a5fa" : "#1d4ed8"),
                                  border: `1px solid ${
                                    isFallback
                                      ? (isDark ? "rgba(217, 119, 6, 0.3)" : "#fde68a")
                                      : (isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe")
                                  }`,
                                }}
                              >
                                {isFallback ? "降级" : "调用"} #{String(att.attempt || i + 1)}
                              </span>
                              <span style={{ fontWeight: 500, color: isDark ? "#c9d1d9" : "#1e293b" }}>
                                {String(att.area || "analysis")}
                              </span>
                              <span className="font-mono" style={{ color: isDark ? "#8b949e" : "#64748b", fontSize: 11 }}>
                                {String(att.provider_id || "default")}
                                {att.model &&
                                String(att.model) !== String(att.provider_id) &&
                                !String(att.provider_id || "").includes(String(att.model))
                                  ? ` / ${String(att.model)}`
                                  : ""}
                              </span>
                            </div>

                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              {att.duration_ms !== undefined && (
                                <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
                                  {Number(att.duration_ms) < 1000
                                    ? `${att.duration_ms}ms`
                                    : `${(Number(att.duration_ms) / 1000).toFixed(1)}s`}
                                </span>
                              )}
                              <span
                                style={{
                                  fontSize: 10,
                                  padding: "1px 5px",
                                  borderRadius: 3,
                                  fontWeight: 500,
                                  background: isSuccess
                                    ? (isDark ? "rgba(22, 163, 74, 0.12)" : "#f0fdf4")
                                    : (isDark ? "rgba(220, 38, 38, 0.12)" : "#fef2f2"),
                                  color: isSuccess
                                    ? (isDark ? "#4ade80" : "#15803d")
                                    : (isDark ? "#f87171" : "#b91c1c"),
                                  border: `1px solid ${
                                    isSuccess
                                      ? (isDark ? "rgba(22, 163, 74, 0.25)" : "#bbf7d0")
                                      : (isDark ? "rgba(220, 38, 38, 0.25)" : "#fecaca")
                                  }`,
                                }}
                              >
                                {isSuccess ? "成功" : "失败"}
                              </span>
                            </div>
                          </div>

                          {hasError && (
                            <div
                              className="font-mono"
                              style={{
                                marginTop: 4,
                                padding: "3px 6px",
                                background: isDark ? "rgba(220, 38, 38, 0.08)" : "#fff1f0",
                                borderLeft: "2px solid #ef4444",
                                borderRadius: "0 3px 3px 0",
                                color: isDark ? "#fca5a5" : "#cf1322",
                                fontSize: 10,
                                wordBreak: "break-all",
                                lineHeight: 1.4,
                              }}
                            >
                              {String(att.error)}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 渲染策略与降级紧凑表格 */}
              {renderAttempts.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    marginBottom: 8,
                    border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                    borderRadius: 4,
                    overflow: "hidden",
                    background: isDark ? "#161b22" : "#ffffff",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "5px 8px",
                      background: isDark ? "#21262d" : "#f8fafc",
                      borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                      fontSize: 11,
                    }}
                  >
                    <span style={{ fontWeight: 600, color: isDark ? "#c9d1d9" : "#334155" }}>
                      图片渲染策略与降级观测
                    </span>
                    <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
                      共 {renderAttempts.length} 轮策略
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column" }}>
                    {renderAttempts.map((att: Record<string, unknown>, i: number) => {
                      const isSuccess = att.status === "success";
                      const hasError = !isSuccess && Boolean(att.error);

                      return (
                        <div
                          key={i}
                          style={{
                            padding: "6px 8px",
                            borderBottom:
                              i < renderAttempts.length - 1
                                ? `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`
                                : "none",
                            fontSize: 11,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 6,
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                              <span
                                className="font-mono"
                                style={{
                                  fontSize: 10,
                                  padding: "1px 5px",
                                  borderRadius: 3,
                                  background: i > 0
                                    ? (isDark ? "rgba(217, 119, 6, 0.15)" : "#fef3c7")
                                    : (isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff"),
                                  color: i > 0
                                    ? (isDark ? "#fbbf24" : "#b45309")
                                    : (isDark ? "#60a5fa" : "#1d4ed8"),
                                  border: `1px solid ${
                                    i > 0
                                      ? (isDark ? "rgba(217, 119, 6, 0.3)" : "#fde68a")
                                      : (isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe")
                                  }`,
                                }}
                              >
                                {i > 0 ? "降级" : "首选"} 第 {String(att.attempt || i + 1)} 轮
                              </span>
                              <span style={{ color: isDark ? "#c9d1d9" : "#1e293b" }}>
                                格式: <b>{String(att.type || "jpeg")}</b>
                                {att.viewport ? ` | 视口: ${String(att.viewport)}` : ""}
                              </span>
                            </div>

                            <span
                              style={{
                                fontSize: 10,
                                padding: "1px 5px",
                                borderRadius: 3,
                                fontWeight: 500,
                                background: isSuccess
                                  ? (isDark ? "rgba(22, 163, 74, 0.12)" : "#f0fdf4")
                                  : (isDark ? "rgba(220, 38, 38, 0.12)" : "#fef2f2"),
                                color: isSuccess
                                  ? (isDark ? "#4ade80" : "#15803d")
                                  : (isDark ? "#f87171" : "#b91c1c"),
                                border: `1px solid ${
                                  isSuccess
                                    ? (isDark ? "rgba(22, 163, 74, 0.25)" : "#bbf7d0")
                                    : (isDark ? "rgba(220, 38, 38, 0.25)" : "#fecaca")
                                }`,
                              }}
                            >
                              {isSuccess ? "渲染成功" : "渲染失败"}
                            </span>
                          </div>

                          {hasError && (
                              <div
                                className="font-mono"
                                style={{
                                  marginTop: 4,
                                  padding: "3px 6px",
                                  background: isDark ? "rgba(220, 38, 38, 0.08)" : "#fff1f0",
                                  borderLeft: "2px solid #ef4444",
                                  borderRadius: "0 3px 3px 0",
                                  color: isDark ? "#fca5a5" : "#cf1322",
                                  fontSize: 10,
                                  wordBreak: "break-all",
                                  lineHeight: 1.4,
                                }}
                              >
                                {String(att.error)}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* LLM 真实提示词 Prompt 检视器 */}
              {(span.stage_name === "LLM_ANALYSIS" ||
                Boolean(span.payload?.prompts)) && (
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
