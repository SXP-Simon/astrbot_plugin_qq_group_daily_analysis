import React, { useRef, useEffect, useState, useCallback } from "react";
import { Card, Tooltip, Typography, Button, Space } from "antd";
import {
  ClockCircleOutlined,
  LeftOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { TraceRecord } from "../../entities/trace/model/types";
import { formatTimestamp, formatDuration, formatTokens } from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";

const { Text } = Typography;

interface AnalysisTimelinePickerProps {
  traces: TraceRecord[];
  selectedTrace: TraceRecord | null;
  onSelectTrace: (trace: TraceRecord) => void;
  onViewTraceDetail?: (traceId: string) => void;
  loading?: boolean;
}

export const AnalysisTimelinePicker: React.FC<AnalysisTimelinePickerProps> = ({
  traces,
  selectedTrace,
  onSelectTrace,
  loading = false,
}) => {
  const { isDark } = useTheme();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const activeNodeRef = useRef<HTMLDivElement>(null);

  // 鼠标拖拽平移状态 (Drag to scroll)
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [hasMoved, setHasMoved] = useState(false);

  const selectedTraceId = selectedTrace?.trace_id;
  const selectedIndex = traces.findIndex((t) => t.trace_id === selectedTraceId);

  // 选中的节点平滑自动居中
  useEffect(() => {
    if (activeNodeRef.current && scrollContainerRef.current) {
      activeNodeRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [selectedTraceId]);

  // 鼠标滚轮横向滑动
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollLeft += e.deltaY;
    }
  };

  // 鼠标按下开始拖动
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrollContainerRef.current) return;
    setIsDragging(true);
    setHasMoved(false);
    setStartX(e.pageX - scrollContainerRef.current.offsetLeft);
    setScrollLeft(scrollContainerRef.current.scrollLeft);
  };

  // 鼠标移动中
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !scrollContainerRef.current) return;
    e.preventDefault();
    const x = e.pageX - scrollContainerRef.current.offsetLeft;
    const walk = (x - startX) * 1.5;
    if (Math.abs(walk) > 4) {
      setHasMoved(true);
    }
    scrollContainerRef.current.scrollLeft = scrollLeft - walk;
  };

  // 鼠标松开/离开
  const handleMouseUpOrLeave = () => {
    setIsDragging(false);
  };

  // 上一条 / 下一条快捷切换
  const handlePrev = useCallback(() => {
    if (selectedIndex > 0) {
      onSelectTrace(traces[selectedIndex - 1]);
    }
  }, [selectedIndex, traces, onSelectTrace]);

  const handleNext = useCallback(() => {
    if (selectedIndex >= 0 && selectedIndex < traces.length - 1) {
      onSelectTrace(traces[selectedIndex + 1]);
    }
  }, [selectedIndex, traces, onSelectTrace]);

  if (!traces || traces.length === 0) {
    return null;
  }

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        background: isDark ? "#161b22" : "#ffffff",
        borderColor: isDark ? "#30363d" : "#e2e8f0",
      }}
    >
      {/* 顶部标题与前后切换控制 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <Space size={6} align="center">
          <ClockCircleOutlined style={{ color: isDark ? "#8b949e" : "#64748b", fontSize: 13 }} />
          <Text strong style={{ fontSize: 13, letterSpacing: "-0.2px", color: isDark ? "#c9d1d9" : "#1e293b" }}>
            时间线
          </Text>
          {selectedIndex >= 0 && (
            <span
              className="font-mono"
              style={{
                fontSize: 11,
                color: isDark ? "#8b949e" : "#64748b",
                marginLeft: 4,
              }}
            >
              ({selectedIndex + 1}/{traces.length})
            </span>
          )}
        </Space>

        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<LeftOutlined style={{ fontSize: 10 }} />}
            disabled={selectedIndex <= 0 || loading}
            onClick={handlePrev}
            style={{ width: 24, height: 24, padding: 0 }}
          />
          <Button
            size="small"
            type="text"
            icon={<RightOutlined style={{ fontSize: 10 }} />}
            disabled={selectedIndex >= traces.length - 1 || loading}
            onClick={handleNext}
            style={{ width: 24, height: 24, padding: 0 }}
          />
        </Space>
      </div>

      {/* 现代化时间线轨道容器 (支持手势拖拽、滚轮横向滚动与节点悬浮微交互) */}
      <div
        ref={scrollContainerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUpOrLeave}
        onMouseLeave={handleMouseUpOrLeave}
        style={{
          position: "relative",
          overflowX: "auto",
          overflowY: "hidden",
          cursor: isDragging ? "grabbing" : "grab",
          userSelect: "none",
          padding: "16px 20px 10px 20px",
          scrollbarWidth: "none",
        }}
      >
        {/* 时间线轴线 */}
        <div
          style={{
            position: "absolute",
            top: 23,
            left: 20,
            right: 20,
            height: 2,
            background: isDark ? "#30363d" : "#e2e8f0",
            zIndex: 1,
          }}
        />

        {/* 节点序列 */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            position: "relative",
            zIndex: 2,
            minWidth: "100%",
            justifyContent: traces.length < 8 ? "space-around" : "flex-start",
            gap: traces.length < 8 ? 0 : 48,
          }}
        >
          {traces.map((trace) => {
            const isSelected = trace.trace_id === selectedTraceId;
            const isSucceeded = trace.status === "succeeded";
            const isFailed = trace.status === "failed";
            const isRunning = trace.status === "running";

            const rawTime = formatTimestamp(trace.started_at);
            // 提取月-日 或 时:分 紧凑展示
            const dateParts = rawTime.split(" ");
            const shortDate = dateParts[0] ? dateParts[0].slice(5) : ""; // MM-DD
            const shortTime = dateParts[1] ? dateParts[1].slice(0, 5) : ""; // HH:mm
            const displayLabel = `${shortDate} ${shortTime}`;

            const tokenTotal = trace.token_usage?.total_tokens ?? 0;
            const compRatio = trace.context_metrics?.compression_ratio
              ? Math.round(trace.context_metrics.compression_ratio * 100)
              : 0;

            // 悬停提示内容 (严谨、紧凑、无任何 Emoji)
            const tooltipContent = (
              <div style={{ fontSize: 12, lineHeight: 1.5, minWidth: 180 }}>
                <div style={{ fontWeight: 600, color: "#ffffff", marginBottom: 4 }}>
                  {trace.group_name || "未知群聊"} ({trace.group_id})
                </div>
                <div style={{ color: "#cbd5e1", fontSize: 11, fontFamily: "monospace" }}>
                  时间: {rawTime}
                </div>
                <div style={{ color: "#cbd5e1", fontSize: 11, fontFamily: "monospace" }}>
                  状态: {isSucceeded ? "分析成功" : isFailed ? "执行失败" : "分析中"}
                </div>
                <div style={{ color: "#cbd5e1", fontSize: 11, fontFamily: "monospace" }}>
                  Token消耗: {formatTokens(tokenTotal)}
                </div>
                {compRatio > 0 && (
                  <div style={{ color: "#cbd5e1", fontSize: 11, fontFamily: "monospace" }}>
                    消息留存比: {compRatio}%
                  </div>
                )}
                {trace.duration_ms && (
                  <div style={{ color: "#cbd5e1", fontSize: 11, fontFamily: "monospace" }}>
                    耗时: {formatDuration(trace.duration_ms)}
                  </div>
                )}
              </div>
            );

            // 节点核心圆点样式
            let dotColor = isDark ? "#475569" : "#cbd5e1";
            if (isSelected) {
              dotColor = "#2563eb";
            } else if (isSucceeded) {
              dotColor = "#16a34a";
            } else if (isFailed) {
              dotColor = "#dc2626";
            } else if (isRunning) {
              dotColor = "#2563eb";
            }

            return (
              <Tooltip key={trace.trace_id} title={tooltipContent} placement="top">
                <div
                  ref={isSelected ? activeNodeRef : null}
                  onClick={() => {
                    if (!hasMoved) {
                      onSelectTrace(trace);
                    }
                  }}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    cursor: "pointer",
                    padding: "4px 6px",
                    transition: "all 0.15s ease",
                  }}
                >
                  {/* 圆点节点 */}
                  <div
                    style={{
                      width: isSelected ? 14 : 10,
                      height: isSelected ? 14 : 10,
                      borderRadius: "50%",
                      backgroundColor: dotColor,
                      boxShadow: isSelected
                        ? isDark
                          ? "0 0 0 4px rgba(37, 99, 235, 0.35)"
                          : "0 0 0 4px rgba(37, 99, 235, 0.2)"
                        : "0 0 0 2px " + (isDark ? "#161b22" : "#ffffff"),
                      transition: "all 0.15s ease",
                      marginBottom: 8,
                    }}
                  />

                  {/* 节点下方时间标签 */}
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 11,
                      fontWeight: isSelected ? 600 : 400,
                      color: isSelected
                        ? "#2563eb"
                        : isDark
                        ? "#8b949e"
                        : "#64748b",
                      whiteSpace: "nowrap",
                      letterSpacing: "-0.3px",
                      transition: "color 0.15s ease",
                    }}
                  >
                    {displayLabel}
                  </span>
                </div>
              </Tooltip>
            );
          })}
        </div>
      </div>
    </Card>
  );
};
