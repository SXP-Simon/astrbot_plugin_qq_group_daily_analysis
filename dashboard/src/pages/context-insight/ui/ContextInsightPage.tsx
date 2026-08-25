import React from "react";
import { Space, Card, Row, Col, Typography, Select } from "antd";
import { DollarOutlined, BranchesOutlined, PieChartOutlined, DatabaseOutlined } from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import { ContextFunnelWidget } from "../../../widgets/context-funnel-widget/ContextFunnelWidget";
import { TokenChartWidget } from "../../../widgets/token-chart-widget/TokenChartWidget";
import { formatTokens, formatCost, formatPercent } from "../../../shared/lib/formatters";
import { useContextInsightViewModel } from "../model/useContextInsightViewModel";

const { Text } = Typography;

interface ContextInsightPageProps {
  viewModel: ReturnType<typeof useContextInsightViewModel>;
}

export const ContextInsightPage: React.FC<ContextInsightPageProps> = ({ viewModel }) => {
  const {
    recentTraces,
    selectedTrace,
    setSelectedTrace,
    contextMetrics,
    tokenUsage,
    loading,
  } = viewModel;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部样本选择工具条 */}
      <Card size="small">
        <Space size="middle" style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap" }}>
          <div>
            <Text strong style={{ fontSize: 13, marginRight: 8 }}>
              🧠 上下文演进与 Token 洞察 (dsh-context Insight)
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              透视消息清洗漏斗、各 Analyzer 提示词占用与 Token 成本
            </Text>
          </div>
          <Space>
            <span style={{ fontSize: 12 }}>选择分析样本:</span>
            <Select
              size="small"
              style={{ width: 240 }}
              value={selectedTrace?.trace_id}
              onChange={(val) => {
                const found = recentTraces.find((t) => t.trace_id === val);
                if (found) setSelectedTrace(found);
              }}
              options={recentTraces.map((t) => ({
                label: `${t.group_name || t.group_id} (${new Date(t.started_at * 1000).toLocaleTimeString()})`,
                value: t.trace_id,
              }))}
            />
          </Space>
        </Space>
      </Card>

      {/* 样本核心数据指标卡片 */}
      <Row gutter={[10, 10]}>
        <Col xs={12} sm={6}>
          <MetricCard
            title="原始摄取消息"
            value={`${contextMetrics.raw_message_count.toLocaleString()} 条`}
            prefix={<DatabaseOutlined style={{ color: "#1677ff" }} />}
            subTitle="IM 协议拉取/增量池"
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="清洗留存率"
            value={formatPercent(contextMetrics.compression_ratio)}
            prefix={<BranchesOutlined style={{ color: "#52c41a" }} />}
            valueStyle={{ color: "#52c41a" }}
            subTitle={`清洗后 ${contextMetrics.cleaned_message_count.toLocaleString()} 条有效`}
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="样本 Token 消耗"
            value={formatTokens(tokenUsage.total_tokens)}
            prefix={<PieChartOutlined style={{ color: "#722ed1" }} />}
            subTitle={`Prompt: ${formatTokens(tokenUsage.prompt_tokens)} / Output: ${formatTokens(tokenUsage.completion_tokens)}`}
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="单次预估成本"
            value={formatCost(tokenUsage.estimated_cost)}
            prefix={<DollarOutlined style={{ color: "#faad14" }} />}
            valueStyle={{ color: "#faad14" }}
            subTitle="基于模型费率计算"
            loading={loading}
          />
        </Col>
      </Row>

      {/* 核心可视化微件 (Widgets Organisms) */}
      <Row gutter={[10, 10]}>
        <Col xs={24} md={12}>
          <ContextFunnelWidget metrics={contextMetrics} />
        </Col>
        <Col xs={24} md={12}>
          <TokenChartWidget tokenUsage={tokenUsage} />
        </Col>
      </Row>
    </Space>
  );
};
