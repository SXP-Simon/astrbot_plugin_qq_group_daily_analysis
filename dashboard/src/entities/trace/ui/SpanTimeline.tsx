import React from "react";
import { Timeline, Tag, Typography, Progress } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { TraceSpan } from "../model/types";
import { formatDuration } from "../../../shared/lib/formatters";

const { Text } = Typography;

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
}

export const SpanTimeline: React.FC<SpanTimelineProps> = ({
  spans,
  totalDurationMs = 1,
}) => {
  if (!spans || spans.length === 0) {
    return <Text type="secondary">无 Span 阶段打点记录</Text>;
  }

  const items = spans.map((span) => {
    let color = "blue";
    let icon = <ClockCircleOutlined />;
    if (span.status === "success" || span.status === "succeeded") {
      color = "green";
      icon = <CheckCircleOutlined />;
    } else if (span.status === "failed" || span.status === "error") {
      color = "red";
      icon = <CloseCircleOutlined />;
    }

    const durationPct = Math.min(
      100,
      Math.max(2, Math.round(((span.duration_ms || 0) / Math.max(1, totalDurationMs)) * 100))
    );

    return {
      color,
      dot: icon,
      children: (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600, fontSize: 12, fontFamily: "monospace" }}>
              {span.stage_name}
            </span>
            <Tag color={color} className="font-mono text-xs">
              {formatDuration(span.duration_ms)}
            </Tag>
          </div>
          <Progress
            percent={durationPct}
            size="small"
            showInfo={false}
            strokeColor={color === "green" ? "#52c41a" : color === "red" ? "#ff4d4f" : "#1677ff"}
            style={{ margin: "3px 0 0 0" }}
          />
        </div>
      ),
    };
  });

  return <Timeline items={items} style={{ marginTop: 12 }} />;
};
