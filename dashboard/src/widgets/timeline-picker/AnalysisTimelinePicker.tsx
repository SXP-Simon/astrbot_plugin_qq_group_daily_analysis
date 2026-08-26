import React, { useEffect, useRef } from "react";
import { Card, Space, Button, Tag, Typography, Tooltip } from "antd";
import {
  LeftOutlined,
  RightOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  TeamOutlined,
  BranchesOutlined,
  PieChartOutlined,
  ClockCircleOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import { TraceRecord } from "../../entities/trace/model/types";
import {
  formatDuration,
  formatSmartTokens,
  formatPercent,
  formatTimestamp,
} from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";

const { Text } = Typography;

interface AnalysisTimelinePickerProps {
  traces: TraceRecord[];
  selectedTrace: TraceRecord | null;
  onSelectTrace: (trace: TraceRecord) => void;
  onViewTraceDetail?: (traceId: string) => void;
}

export const AnalysisTimelinePicker: React.FC<AnalysisTimelinePickerProps> = ({
  traces,
  selectedTrace,
  onSelectTrace,
  onViewTraceDetail,
}) => {
  const { isDark } = useTheme();
  const railRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const currentIndex = selectedTrace
    ? traces.findIndex((t) => t.trace_id === selectedTrace.trace_id)
    : -1;

  // 当选中的 Trace 发生变化时，平滑将对应卡片滚动至时间轴中央可视区域
  useEffect(() => {
    if (selectedTrace) {
      const el = itemRefs.current.get(selectedTrace.trace_id);
      if (el && typeof el.scrollIntoView === "function") {
        el.scrollIntoView({
          behavior: "smooth",
          inline: "center",
          block: "nearest",
        });
      }
    }
  }, [selectedTrace]);

  const handlePrev = () => {
    if (currentIndex > 0) {
      onSelectTrace(traces[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    if (currentIndex >= 0 && currentIndex < traces.length - 1) {
      onSelectTrace(traces[currentIndex + 1]);
    }
  };

  if (traces.length === 0) {
    return null;
  }

  return (
    <Card
      size="small"
      style={{
        background: isDark ? "rgba(20, 20, 24, 0.75)" : "#fafafa",
        border: `1px solid ${isDark ? "#303030" : "#f0f0f0"}`,
      }}
      bodyStyle={{ padding: "8px 12px" }}
    >
      {/* 头部控制栏：标题 + 前后导航切换 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <Space size={8} align="center">
          <Text strong style={{ fontSize: 12, color: isDark ? "#d9d9d9" : "#595959" }}>
            ⏱️ 时序事件样本轴
          </Text>
          <Tag color="blue" style={{ margin: 0, fontSize: 11, lineHeight: "18px", padding: "0 6px" }}>
            {currentIndex >= 0 ? `${currentIndex + 1} / ${traces.length}` : `${traces.length} 条样本`}
          </Tag>
          {selectedTrace && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              当前选中: <b>{selectedTrace.group_name || selectedTrace.group_id}</b> ({formatTimestamp(selectedTrace.started_at)})
            </Text>
          )}
        </Space>

        <Space size={4}>
          <Tooltip title="切换上一个样本 (快捷键 ←)">
            <Button
              size="small"
              icon={<LeftOutlined />}
              disabled={currentIndex <= 0}
              onClick={handlePrev}
            />
          </Tooltip>
          <Tooltip title="切换下一个样本 (快捷键 →)">
            <Button
              size="small"
              icon={<RightOutlined />}
              disabled={currentIndex < 0 || currentIndex >= traces.length - 1}
              onClick={handleNext}
            />
          </Tooltip>
        </Space>
      </div>

      {/* 水平时间轴滚动轨道 */}
      <div
        ref={railRef}
        style={{
          display: "flex",
          gap: 10,
          overflowX: "auto",
          paddingBottom: 6,
          paddingTop: 2,
          scrollBehavior: "smooth",
        }}
      >
        {traces.map((trace, idx) => {
          const isSelected = selectedTrace?.trace_id === trace.trace_id;
          const isSuccess = trace.status === "succeeded";
          const isFailed = trace.status === "failed";

          return (
            <div
              key={trace.trace_id}
              ref={(el) => {
                if (el) itemRefs.current.set(trace.trace_id, el);
                else itemRefs.current.delete(trace.trace_id);
              }}
              onClick={() => onSelectTrace(trace)}
              style={{
                flexShrink: 0,
                width: 210,
                cursor: "pointer",
                padding: "8px 10px",
                borderRadius: 6,
                background: isSelected
                  ? isDark
                    ? "rgba(22, 119, 255, 0.18)"
                    : "#e6f4ff"
                  : isDark
                    ? "#141414"
                    : "#ffffff",
                border: isSelected
                  ? "1.5px solid #1677ff"
                  : `1px solid ${isDark ? "#303030" : "#e8e8e8"}`,
                boxShadow: isSelected
                  ? isDark
                    ? "0 0 12px rgba(22, 119, 255, 0.4)"
                    : "0 2px 8px rgba(22, 119, 255, 0.25)"
                  : "none",
                transition: "all 0.2s ease-in-out",
                position: "relative",
              }}
            >
              {/* 顶部：时间戳 + 状态徽章 */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 4,
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: isSelected ? "#1677ff" : isDark ? "#8c8c8c" : "#8c8c8c",
                  }}
                >
                  #{idx + 1} {formatTimestamp(trace.started_at).slice(5)}
                </Text>
                <Tag
                  color={isSuccess ? "success" : isFailed ? "error" : "processing"}
                  icon={
                    isSuccess ? (
                      <CheckCircleOutlined />
                    ) : isFailed ? (
                      <CloseCircleOutlined />
                    ) : (
                      <SyncOutlined spin />
                    )
                  }
                  style={{ margin: 0, fontSize: 10, lineHeight: "16px", padding: "0 4px" }}
                >
                  {isSuccess ? "完成" : isFailed ? "失败" : "运行中"}
                </Tag>
              </div>

              {/* 中间：群聊名称与群号 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  marginBottom: 6,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                <TeamOutlined style={{ color: "#8c8c8c", fontSize: 12, flexShrink: 0 }} />
                <Text
                  strong
                  ellipsis
                  style={{
                    fontSize: 12,
                    color: isSelected ? (isDark ? "#ffffff" : "#0958d9") : undefined,
                  }}
                >
                  {trace.group_name || trace.group_id}
                </Text>
              </div>

              {/* 底部指标：Token消耗 / 留存率 / 耗时 */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: 11,
                  color: isDark ? "#a6a6a6" : "#595959",
                  paddingTop: 4,
                  borderTop: `1px dashed ${isDark ? "#282828" : "#f0f0f0"}`,
                }}
              >
                <span title="模型 Token 消耗">
                  <PieChartOutlined style={{ color: "#722ed1", marginRight: 2 }} />
                  {formatSmartTokens(trace.total_tokens || 0)}
                </span>
                <span title="有效消息留存率">
                  <BranchesOutlined style={{ color: "#52c41a", marginRight: 2 }} />
                  {formatPercent(trace.compression_ratio || 0)}
                </span>
                <span title="分析耗时">
                  <ClockCircleOutlined style={{ color: "#fa8c16", marginRight: 2 }} />
                  {formatDuration(trace.duration_ms || 0)}
                </span>
              </div>

              {/* 选中的微卡片右上角查看任务详情快捷入口 */}
              {isSelected && onViewTraceDetail && (
                <div style={{ position: "absolute", top: -6, right: -6 }}>
                  <Tooltip title="查看此任务执行明细">
                    <Button
                      size="small"
                      type="primary"
                      shape="circle"
                      icon={<EyeOutlined style={{ fontSize: 10 }} />}
                      style={{ width: 18, height: 18, minWidth: 18, fontSize: 10 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewTraceDetail(trace.trace_id);
                      }}
                    />
                  </Tooltip>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
