import React from "react";
import { Tag, Progress, Space, Tooltip, theme } from "antd";
import {
  SyncOutlined,
  WarningOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { getStageSlaThreshold } from "../model/sla";
import { formatDuration, formatStageName } from "../../../shared/lib/formatters";

interface SpanHeaderProps {
  stageName: string;
  durationMs?: number | null;
  startedAt: number;
  totalDurationMs: number;
  status: string;
  isExpanded: boolean;
  onToggleExpand: () => void;
  payload?: Record<string, unknown>;
}

export const SpanHeader: React.FC<SpanHeaderProps> = ({
  stageName,
  durationMs,
  startedAt,
  totalDurationMs,
  status,
  isExpanded,
  onToggleExpand,
  payload,
}) => {
  const { token } = theme.useToken();

  const isRunning = status === "running";
  const duration =
    durationMs !== null && durationMs !== undefined
      ? durationMs
      : Math.max(0, Math.round((Date.now() / 1000 - (startedAt || Date.now() / 1000)) * 1000));

  const durationPct = isRunning
    ? 100
    : Math.min(100, Math.max(2, Math.round((duration / Math.max(1, totalDurationMs)) * 100)));

  const { thresholdMs, description: slaDesc } = getStageSlaThreshold(stageName);
  const isSlaExceeded = !isRunning && duration > thresholdMs;

  const enabledFeatures = payload?.enabled_features as Record<string, boolean> | undefined;
  const enabledCount = enabledFeatures
    ? Object.values(enabledFeatures).filter(Boolean).length
    : 0;
  const hasLlmOutput =
    Number(payload?.topics_count || 0) > 0 ||
    Number(payload?.user_titles_count || 0) > 0 ||
    Number(payload?.golden_quotes_count || 0) > 0 ||
    Boolean(payload?.chat_quality_review);

  // 当开启了 LLM 分析，但产出全为 0 且存在子任务报错/重试耗尽：判定为完全失败 (failed)
  const isAllSubtasksFailed =
    stageName === "LLM_ANALYSIS" &&
    enabledCount > 0 &&
    !hasLlmOutput &&
    (Array.isArray(payload?.subtask_errors) && payload.subtask_errors.length > 0);

  const isFailed =
    status === "failed" ||
    status === "error" ||
    Boolean(payload?.error) ||
    isAllSubtasksFailed;

  const isWarning =
    !isFailed &&
    (status === "warning" ||
      status === "partial_success" ||
      Boolean(payload?.warning) ||
      (Array.isArray(payload?.subtask_errors) && payload.subtask_errors.length > 0));

  let color = "#52c41a";
  let tagColor = "success";

  if (isFailed) {
    color = "#ff4d4f";
    tagColor = "error";
  } else if (isRunning) {
    color = "#1677ff";
    tagColor = "processing";
  } else if (isWarning) {
    color = "#fa8c16";
    tagColor = "warning";
  } else if (isSlaExceeded) {
    color = "#fa8c16";
    tagColor = "warning";
  }

  return (
    <>
      <div
        onClick={onToggleExpand}
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
            {formatStageName(stageName)}
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
              ? `告警 (${formatDuration(durationMs ?? 0)})`
              : isFailed
              ? `失败 (${formatDuration(durationMs ?? 0)})`
              : formatDuration(durationMs ?? 0)}
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
    </>
  );
};
