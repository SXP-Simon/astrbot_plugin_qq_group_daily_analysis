import React from "react";
import { Row, Col } from "antd";
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  HddOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../../shared/ui/MetricCard";
import { formatTimestamp } from "../../../../shared/lib/formatters";
import { IncrementalCursorInfo } from "../../../../entities/plugin-data/model/types";

interface IncrementalCursorCardsProps {
  cursor: IncrementalCursorInfo;
  batchCount: number;
}

export const IncrementalCursorCards: React.FC<IncrementalCursorCardsProps> = ({
  cursor,
  batchCount,
}) => {
  return (
    <Row gutter={[10, 10]}>
      <Col xs={12} sm={6}>
        <MetricCard
          title="上次分析推进时间 (游标)"
          value={
            cursor.last_analyzed_timestamp > 0
              ? formatTimestamp(cursor.last_analyzed_timestamp)
              : "未分析 (初始 0)"
          }
          prefix={<ClockCircleOutlined style={{ color: "#1677ff" }} />}
          subTitle="增量扫描起始基准时间戳"
        />
      </Col>

      <Col xs={12} sm={6}>
        <MetricCard
          title="最新包含消息时间"
          value={
            cursor.last_message_timestamp > 0
              ? formatTimestamp(cursor.last_message_timestamp)
              : "-"
          }
          prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
          subTitle="最近批次涵盖的最新消息戳"
        />
      </Col>

      <Col xs={12} sm={6}>
        <MetricCard
          title="已记录去重消息指纹"
          value={cursor.tracked_message_ids_count.toLocaleString()}
          prefix={<HddOutlined style={{ color: "#722ed1" }} />}
          subTitle="避免跨批次重复统计的消息 ID 集合"
        />
      </Col>

      <Col xs={12} sm={6}>
        <MetricCard
          title="累计暂存批次数"
          value={batchCount.toString()}
          prefix={<ThunderboltOutlined style={{ color: "#fa8c16" }} />}
          subTitle="待最终日报合并汇总的批次总数"
        />
      </Col>
    </Row>
  );
};
