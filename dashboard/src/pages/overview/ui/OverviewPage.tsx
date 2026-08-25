import React from "react";
import { Row, Col, Space, Card } from "antd";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  PieChartOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import { ActiveTaskBoard } from "../../../widgets/active-task-board/ActiveTaskBoard";
import { formatDuration, formatSmartTokens } from "../../../shared/lib/formatters";
import { useOverviewViewModel } from "../model/useOverviewViewModel";

interface OverviewPageProps {
  viewModel: ReturnType<typeof useOverviewViewModel>;
  onOpenTrigger: () => void;
  onViewTrace: (traceId: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  viewModel,
  onOpenTrigger,
  onViewTrace,
}) => {
  const { metrics, activeTasks, loading, handleCancelTask } = viewModel;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部统计卡片矩阵 (KPI Grid) */}
      <Row gutter={[10, 10]}>
        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="今日分析次数"
            value={metrics.today_traces}
            prefix={<ThunderboltOutlined style={{ color: "#1677ff" }} />}
            subTitle={`覆盖 ${metrics.today_active_groups} 个群聊`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="历史总运行"
            value={metrics.total_traces}
            prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
            valueStyle={{ color: "#52c41a" }}
            subTitle={`成功率: ${metrics.success_rate}%`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="平均耗时"
            value={formatDuration(metrics.avg_duration_ms)}
            prefix={<ClockCircleOutlined style={{ color: "#fa8c16" }} />}
            valueStyle={{ color: "#fa8c16" }}
            subTitle="平均端到端耗时"
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="今日模型消耗"
            value={formatSmartTokens(metrics.today_tokens_spent)}
            prefix={<PieChartOutlined style={{ color: "#722ed1" }} />}
            subTitle="今日大模型消耗总量"
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="30天模型消耗"
            value={formatSmartTokens(metrics.total_tokens_spent)}
            prefix={<PieChartOutlined style={{ color: "#13c2c2" }} />}
            subTitle="近30天累计消耗总量"
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="今日分析群聊"
            value={metrics.today_active_groups}
            prefix={<TeamOutlined style={{ color: "#eb2f96" }} />}
            subTitle="今日已分析群数"
            loading={loading}
          />
        </Col>
      </Row>

      {/* 正在运行中的任务看板 (Active Tasks Organism) */}
      <Card size="small">
        <ActiveTaskBoard
          tasks={activeTasks}
          onCancelTask={handleCancelTask}
          onViewTrace={onViewTrace}
          onOpenTrigger={onOpenTrigger}
        />
      </Card>
    </Space>
  );
};
