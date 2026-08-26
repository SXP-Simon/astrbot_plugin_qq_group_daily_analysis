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
  // 持久化保存每个节点元素的引用，杜绝单 ref 切换导致的竞态与归零回退
  const nodeRefs = useRef<(HTMLDivElement | null)[]>([]);

  // 鼠标拖拽平移状态 (Drag to scroll)
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [hasMoved, setHasMoved] = useState(false);

  const selectedTraceId = selectedTrace?.trace_id;
  const selectedIndex = traces.findIndex((t) => t.trace_id === selectedTraceId);

  // 绝对坐标精准居中算法：基于 node.offsetLeft 绝对内层偏移量，100% 确定性居中
  const scrollToTraceIndex = useCallback(
    (index: number, behavior: ScrollBehavior = "smooth") => {
      const container = scrollContainerRef.current;
      const node = nodeRefs.current[index];
      if (!container || !node) return;

      const nodeLeft = node.offsetLeft;
      const nodeWidth = node.offsetWidth;
      const containerWidth = container.clientWidth;

      // 目标位置：使节点中心精确位于可视窗口中心
      const targetScrollLeft = nodeLeft + nodeWidth / 2 - containerWidth / 2;
      const maxScrollLeft = Math.max(0, container.scrollWidth - containerWidth);
      const clampedLeft = Math.max(0, Math.min(maxScrollLeft, targetScrollLeft));

      container.scrollTo({
        left: clampedLeft,
        behavior,
      });
    },
    []
  );

  // 当选中项发生变更时，确保在 DOM 挂载稳定后平滑居中聚焦
  useEffect(() => {
    if (selectedIndex >= 0) {
      const rafId = requestAnimationFrame(() => {
        scrollToTraceIndex(selectedIndex, "smooth");
      });
      return () => cancelAnimationFrame(rafId);
    }
  }, [selectedIndex, scrollToTraceIndex]);

  // 初次载入或数据源重置时，执行一次对齐
  useEffect(() => {
    if (traces.length > 0 && selectedIndex >= 0) {
      const timer = setTimeout(() => {
        scrollToTraceIndex(selectedIndex, "auto");
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [traces.length]); // eslint-disable-line react-hooks/exhaustive-deps

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
      styles={{ body: { padding: "12px 14px" } }}
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
                marginLeft: 2,
              }}
            >
              ({selectedIndex + 1}/{traces.length})
            </span>
          )}
          <span
            style={{
              fontSize: 11,
              background: isDark ? "rgba(37, 99, 235, 0.15)" : "rgba(37, 99, 235, 0.08)",
              color: isDark ? "#60a5fa" : "#2563eb",
              borderRadius: 12,
              padding: "1px 8px",
              marginLeft: 4,
              fontWeight: 500,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            ← 最新事件在左侧 (按时间倒序)
          </span>
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

      {/* 现代化时间线轨道外层滚动容器 */}
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
          padding: "24px 12px 12px 12px",
          scrollbarWidth: "none",
        }}
      >
        {/* 内部完整宽度容器：确保主轴线自始至终贯穿全部节点 */}
        <div
          style={{
            position: "relative",
            display: "inline-flex",
            minWidth: "100%",
            width: "max-content",
            padding: "0 24px",
            alignItems: "center",
            justifyContent: traces.length < 8 ? "space-around" : "flex-start",
            gap: traces.length < 8 ? 0 : 48,
          }}
        >
          {/* 连续主轴线：宽度 100% 自动对齐内部 max-content 完整宽度 */}
          <div
            style={{
              position: "absolute",
              top: 7,
              left: 24,
              right: 24,
              height: 2,
              background: isDark ? "#30363d" : "#e2e8f0",
              zIndex: 1,
            }}
          />

          {/* 节点序列 */}
          {traces.map((trace, idx) => {
            const isSelected = trace.trace_id === selectedTraceId;
            const isSucceeded = trace.status === "succeeded";
            const isFailed = trace.status === "failed";
            const isRunning = trace.status === "running";

            const rawTime = formatTimestamp(trace.started_at);
            const dateParts = rawTime.split(" ");
            const shortDate = dateParts[0] ? dateParts[0].slice(5) : ""; // MM-DD
            const shortTime = dateParts[1] ? dateParts[1].slice(0, 5) : ""; // HH:mm
            const displayLabel = `${shortDate} ${shortTime}`;

            const tokenTotal = trace.token_usage?.total_tokens ?? 0;
            const compRatio = trace.context_metrics?.compression_ratio
              ? Math.round(trace.context_metrics.compression_ratio * 100)
              : 0;

            const tooltipContent = (
              <div style={{ fontSize: 12, lineHeight: 1.6, minWidth: 180, padding: "2px 0" }}>
                <div
                  style={{
                    fontWeight: 600,
                    color: isDark ? "#ffffff" : "#0f172a",
                    marginBottom: 4,
                    borderBottom: `1px solid ${isDark ? "#334155" : "#f1f5f9"}`,
                    paddingBottom: 4,
                  }}
                >
                  {trace.group_name || "未知群聊"} ({trace.group_id})
                </div>
                <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 11, fontFamily: "monospace" }}>
                  时间: {rawTime}
                </div>
                <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 11, fontFamily: "monospace" }}>
                  状态:{" "}
                  <span
                    style={{
                      color: isSucceeded ? "#16a34a" : isFailed ? "#dc2626" : "#2563eb",
                      fontWeight: 600,
                    }}
                  >
                    {isSucceeded ? "分析成功" : isFailed ? "执行失败" : "分析中"}
                  </span>
                </div>
                <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 11, fontFamily: "monospace" }}>
                  Token消耗: <b style={{ color: isDark ? "#ffffff" : "#0f172a" }}>{formatTokens(tokenTotal)}</b>
                </div>
                {compRatio > 0 && (
                  <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 11, fontFamily: "monospace" }}>
                    消息留存比: <b style={{ color: isDark ? "#ffffff" : "#0f172a" }}>{compRatio}%</b>
                  </div>
                )}
                {trace.duration_ms && (
                  <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 11, fontFamily: "monospace" }}>
                    耗时: <b style={{ color: isDark ? "#ffffff" : "#0f172a" }}>{formatDuration(trace.duration_ms)}</b>
                  </div>
                )}
              </div>
            );

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
              <Tooltip
                key={trace.trace_id}
                title={tooltipContent}
                placement="top"
                mouseEnterDelay={0.15}
                color={isDark ? "#1e293b" : "#ffffff"}
                overlayInnerStyle={{
                  color: isDark ? "#ffffff" : "#1e293b",
                  border: `1px solid ${isDark ? "#334155" : "#e2e8f0"}`,
                  boxShadow: isDark
                    ? "0 4px 16px rgba(0, 0, 0, 0.45)"
                    : "0 4px 16px rgba(0, 0, 0, 0.08)",
                  borderRadius: 6,
                  padding: "8px 12px",
                }}
              >
                <div
                  ref={(el) => {
                    nodeRefs.current[idx] = el;
                  }}
                  onClick={() => {
                    if (!hasMoved) {
                      onSelectTrace(trace);
                      scrollToTraceIndex(idx, "smooth");
                    }
                  }}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    cursor: "pointer",
                    zIndex: 2,
                    padding: "0 4px",
                    position: "relative",
                  }}
                >
                  {/* 最左端（最新）或最右端（较早）轻量徽标指示 */}
                  {idx === 0 && (
                    <span
                      style={{
                        position: "absolute",
                        top: -18,
                        fontSize: 10,
                        lineHeight: "14px",
                        fontWeight: 600,
                        color: isDark ? "#60a5fa" : "#2563eb",
                        background: isDark ? "rgba(37,99,235,0.25)" : "#dbeafe",
                        border: `1px solid ${isDark ? "rgba(37,99,235,0.4)" : "#bfdbfe"}`,
                        padding: "0 4px",
                        borderRadius: 3,
                        whiteSpace: "nowrap",
                      }}
                    >
                      最新
                    </span>
                  )}
                  {idx === traces.length - 1 && traces.length > 1 && (
                    <span
                      style={{
                        position: "absolute",
                        top: -18,
                        fontSize: 10,
                        lineHeight: "14px",
                        fontWeight: 500,
                        color: isDark ? "#8b949e" : "#64748b",
                        background: isDark ? "#21262d" : "#f1f5f9",
                        border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                        padding: "0 4px",
                        borderRadius: 3,
                        whiteSpace: "nowrap",
                      }}
                    >
                      较早
                    </span>
                  )}

                  {/* 圆形节点 (含光晕与选中环) */}
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: isSelected
                        ? (isDark ? "#1e293b" : "#ffffff")
                        : (isDark ? "#161b22" : "#ffffff"),
                      border: isSelected
                        ? `3px solid ${dotColor}`
                        : `2px solid ${isDark ? "#30363d" : "#ffffff"}`,
                      boxShadow: isSelected
                        ? "0 0 0 3px rgba(37, 99, 235, 0.25)"
                        : "0 1px 2px rgba(0, 0, 0, 0.1)",
                      transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                      transform: isSelected ? "scale(1.25)" : "scale(1)",
                    }}
                  >
                    <div
                      style={{
                        width: isSelected ? 6 : 8,
                        height: isSelected ? 6 : 8,
                        borderRadius: "50%",
                        background: dotColor,
                      }}
                    />
                  </div>

                  {/* 节点下方时间标签 */}
                  <span
                    className="font-mono"
                    style={{
                      marginTop: 8,
                      fontSize: 11,
                      color: isSelected
                        ? (isDark ? "#58a6ff" : "#2563eb")
                        : (isDark ? "#8b949e" : "#64748b"),
                      fontWeight: isSelected ? 600 : 400,
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
