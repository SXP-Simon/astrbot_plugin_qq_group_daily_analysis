import React from "react";
import { Card, Progress, Descriptions, Typography } from "antd";
import { DatabaseOutlined } from "@ant-design/icons";
import { ContextMetrics } from "../../entities/trace/model/types";
import { formatPercent } from "../../shared/lib/formatters";

const { Text } = Typography;

interface ContextFunnelWidgetProps {
  metrics: ContextMetrics;
}

export const ContextFunnelWidget: React.FC<ContextFunnelWidgetProps> = ({ metrics }) => {
  const compressionPct = Math.round((metrics.compression_ratio || 0) * 100);

  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 13 }}>
          <DatabaseOutlined style={{ color: "#1677ff", marginRight: 6 }} />
          消息清洗与过滤统计
        </span>
      }
    >
      <div style={{ padding: "8px 0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <Text style={{ fontSize: 12 }}>有效消息留存率</Text>
          <Text strong style={{ fontSize: 12 }}>
            {formatPercent(metrics.compression_ratio)}
          </Text>
        </div>
        <Progress
          percent={compressionPct}
          status="active"
          strokeColor={{ from: "#108ee9", to: "#87d068" }}
        />
      </div>

      <Descriptions size="small" column={1} bordered style={{ marginTop: 12 }}>
        <Descriptions.Item label="读取原始消息">
          <span className="font-mono">{metrics.raw_message_count.toLocaleString()} 条</span>
        </Descriptions.Item>
        <Descriptions.Item label="过滤后有效消息">
          <span className="font-mono font-semibold" style={{ color: "#52c41a" }}>
            {metrics.cleaned_message_count.toLocaleString()} 条
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="剔除的无效消息">
          <span className="font-mono" style={{ color: "#8c8c8c" }}>
            {(metrics.raw_message_count - metrics.cleaned_message_count).toLocaleString()} 条
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="分批处理批次">
          <span className="font-mono">{metrics.incremental_batches || 1} 批</span>
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
};
