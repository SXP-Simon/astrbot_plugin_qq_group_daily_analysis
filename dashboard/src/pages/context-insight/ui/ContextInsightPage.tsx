import React from "react";
import { Space, Card, Row, Col, Typography, Select } from "antd";
import { BranchesOutlined, PieChartOutlined, DatabaseOutlined, BarChartOutlined, FilterOutlined } from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import { ContextFunnelWidget } from "../../../widgets/context-funnel-widget/ContextFunnelWidget";
import { TokenChartWidget } from "../../../widgets/token-chart-widget/TokenChartWidget";
import { formatSmartTokens, formatPercent } from "../../../shared/lib/formatters";
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
              <BarChartOutlined style={{ color: "#1677ff", marginRight: 6 }} />
              消息统计与模型消耗
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              查看群聊消息过滤留存情况与各分析模块的模型消耗分布
            </Text>
          </div>
          <Space>
            <span style={{ fontSize: 12 }}>选择记录:</span>
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
            title="读取消息数"
            value={`${contextMetrics.raw_message_count.toLocaleString()} 条`}
            prefix={<DatabaseOutlined style={{ color: "#1677ff" }} />}
            subTitle="从聊天记录抓取"
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="有效消息留存率"
            value={formatPercent(contextMetrics.compression_ratio)}
            prefix={<BranchesOutlined style={{ color: "#52c41a" }} />}
            valueStyle={{ color: "#52c41a" }}
            subTitle={`过滤后 ${contextMetrics.cleaned_message_count.toLocaleString()} 条有效`}
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="本次模型消耗"
            value={formatSmartTokens(tokenUsage.total_tokens)}
            prefix={<PieChartOutlined style={{ color: "#722ed1" }} />}
            subTitle={`输入: ${formatSmartTokens(tokenUsage.prompt_tokens)} / 输出: ${formatSmartTokens(tokenUsage.completion_tokens)}`}
            loading={loading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <MetricCard
            title="剔除噪音消息"
            value={`${Math.max(0, contextMetrics.raw_message_count - contextMetrics.cleaned_message_count).toLocaleString()} 条`}
            prefix={<FilterOutlined style={{ color: "#faad14" }} />}
            valueStyle={{ color: "#faad14" }}
            subTitle="广告/空消息/噪音指令"
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
