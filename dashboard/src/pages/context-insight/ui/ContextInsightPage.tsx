import React from "react";
import { Space, Card, Row, Col, Typography, Select, Empty, Tag } from "antd";
import {
  BranchesOutlined,
  PieChartOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  FilterOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import { ContextFunnelWidget } from "../../../widgets/context-funnel-widget/ContextFunnelWidget";
import { TokenChartWidget } from "../../../widgets/token-chart-widget/TokenChartWidget";
import { TraceFilterBar } from "../../../features/filter-traces/ui/TraceFilterBar";
import { AnalysisTimelinePicker } from "../../../widgets/timeline-picker/AnalysisTimelinePicker";
import {
  formatSmartTokens,
  formatPercent,
  formatTimestamp,
} from "../../../shared/lib/formatters";
import { useContextInsightViewModel } from "../model/useContextInsightViewModel";

const { Text } = Typography;

interface ContextInsightPageProps {
  viewModel: ReturnType<typeof useContextInsightViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export const ContextInsightPage: React.FC<ContextInsightPageProps> = ({
  viewModel,
  onViewTrace,
}) => {
  const {
    traces,
    total,
    selectedTrace,
    setSelectedTrace,
    contextMetrics,
    tokenUsage,
    loading,
    search,
    selectedGroup,
    statusFilter,
    groups,
    setSearch,
    setSelectedGroup,
    setStatusFilter,
    setDateRange,
    refresh,
  } = viewModel;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部过滤筛选与记录选择工具条 */}
      <Card size="small">
        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ fontSize: 13, marginRight: 8 }}>
            <BarChartOutlined style={{ color: "#1677ff", marginRight: 6 }} />
            消息统计与模型消耗
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            查看群聊消息过滤留存情况与各分析模块的模型消耗分布
          </Text>
        </div>

        {/* 统一的多维筛选工具条 */}
        <TraceFilterBar
          search={search}
          selectedGroup={selectedGroup}
          statusFilter={statusFilter}
          groups={groups}
          loading={loading}
          onSearchChange={setSearch}
          onGroupChange={setSelectedGroup}
          onStatusChange={setStatusFilter}
          onDateRangeChange={setDateRange}
          onRefresh={refresh}
        />

        {/* 目标分析记录切换下拉框 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 8,
            marginTop: 4,
            paddingTop: 8,
            borderTop: "1px dashed rgba(140, 140, 140, 0.15)",
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "#8c8c8c",
              flexShrink: 0,
            }}
          >
            <ScheduleOutlined style={{ marginRight: 4 }} />
            选择目标分析样本 ({traces.length} 条已载入
            {total > traces.length ? ` / 共 ${total} 条` : ""}):
          </span>
          <Select
            size="small"
            style={{ flex: 1, minWidth: 320 }}
            placeholder={
              traces.length === 0
                ? "暂无符合条件的分析记录"
                : "请选择要查看统计与消耗的任务记录"
            }
            value={selectedTrace?.trace_id}
            disabled={traces.length === 0}
            showSearch
            optionFilterProp="label"
            onChange={(val) => {
              const found = traces.find((t) => t.trace_id === val);
              if (found) setSelectedTrace(found);
            }}
            options={traces.map((t) => {
              const statusText =
                t.status === "succeeded"
                  ? "成功"
                  : t.status === "failed"
                    ? "失败"
                    : t.status === "running"
                      ? "运行中"
                      : t.status || "未知";
              const groupName = t.group_name || "未知群";
              const timeStr = formatTimestamp(t.started_at);
              return {
                label: `${groupName} (${t.group_id}) · ${timeStr} · [${t.trace_id}] (${statusText})`,
                value: t.trace_id,
              };
            })}
          />
          {selectedTrace && (
            <Tag color={selectedTrace.status === "succeeded" ? "success" : "default"} style={{ margin: 0 }}>
              {selectedTrace.status === "succeeded" ? "已完成" : selectedTrace.status}
            </Tag>
          )}
        </div>
      </Card>

      {/* 时序事件样本轴 (Timeline Event Rail) */}
      {traces.length > 0 && (
        <AnalysisTimelinePicker
          traces={traces}
          selectedTrace={selectedTrace}
          onSelectTrace={setSelectedTrace}
          onViewTraceDetail={onViewTrace}
        />
      )}

      {traces.length === 0 && !loading ? (
        <Card size="small" style={{ minHeight: 360, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无符合条件的分析记录，请调整筛选条件或触发新分析"
            style={{ margin: "48px 0" }}
          />
        </Card>
      ) : (
        <>
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
        </>
      )}
    </Space>
  );
};
