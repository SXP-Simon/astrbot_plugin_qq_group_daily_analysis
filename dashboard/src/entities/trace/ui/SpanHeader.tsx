import React from "react";
import { Tag, Progress, Space, Tooltip, theme } from "antd";
import {
  SyncOutlined,
  WarningOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { resolveSpanOutcome } from "../model/spanOutcome";
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
  parentStageName?: string;
  hasChildren?: boolean;
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
  parentStageName,
  hasChildren = false,
}) => {
  const { token } = theme.useToken();

  const outcome = resolveSpanOutcome(status, payload);
  const isRunning = outcome === "running";
  const isCancelled = outcome === "cancelled";
  const duration =
    durationMs !== null && durationMs !== undefined
      ? durationMs
      : Math.max(0, Math.round((Date.now() / 1000 - (startedAt || Date.now() / 1000)) * 1000));

  const durationPct = isRunning
    ? 100
    : Math.min(100, Math.max(0, (duration / Math.max(1, totalDurationMs)) * 100));
  const durationPercentLabel = durationPct > 0 && durationPct < 0.1
    ? "<0.1"
    : durationPct.toFixed(1).replace(/\.0$/, "");

  const { thresholdMs, description: slaDesc } = getStageSlaThreshold(stageName);
  const isSlaExceeded = !isRunning && !isCancelled && duration > thresholdMs;
  const isFailed = outcome === "failed";
  const isWarning = outcome === "warning";

  let color = "#52c41a";
  let tagColor = "success";

  if (isCancelled) {
    color = token.colorTextDisabled;
    tagColor = "default";
  } else if (isFailed) {
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
            {stageName === "IMAGE_RENDER_ATTEMPT" && typeof payload?.strategy_name === "string" && <span style={{ fontWeight: 400 }}> · {payload.strategy_name}</span>}
          </span>
          {hasChildren && <Tag style={{ margin: 0, fontSize: 10 }}>含子阶段</Tag>}
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
            <Tooltip title={parentStageName ? `相对于「${formatStageName(parentStageName)}」的耗时，父子阶段不能重复累加` : "相对于本次任务的总耗时"}>
              <span style={{ fontSize: 11, color: token.colorTextSecondary, whiteSpace: "nowrap" }}>
                {parentStageName ? "占父阶段" : "占总耗时"} {durationPercentLabel}%
              </span>
            </Tooltip>
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
            {isCancelled
              ? `已取消 (${formatDuration(durationMs ?? 0)})`
              : isRunning
              ? `执行中 (${formatDuration(duration)})`
              : isWarning
              ? `警告 (${formatDuration(durationMs ?? 0)})`
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
