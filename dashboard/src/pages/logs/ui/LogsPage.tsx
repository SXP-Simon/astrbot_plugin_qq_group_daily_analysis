import React, { useRef } from "react";
import { Card, Tag, Empty, message } from "antd";
import { useLogsViewModel } from "../model/useLogsViewModel";
import { LogFilterBar } from "../../../features/filter-logs/ui/LogFilterBar";
import { PluginLogItem, TAG_STYLE_MAP } from "../../../entities/log/model/types";
import { useTheme } from "../../../shared/lib/useTheme";
import { copyToClipboard } from "../../../shared/lib/clipboard";

interface LogsPageProps {
  viewModel: ReturnType<typeof useLogsViewModel>;
  onViewTrace: (traceId: string) => void;
}

export const LogsPage: React.FC<LogsPageProps> = ({
  viewModel,
  onViewTrace,
}) => {
  const { isDark } = useTheme();
  const logBoxRef = useRef<HTMLDivElement>(null);

  const {
    logs,
    total,
    availableTags,
    loading,
    search,
    setSearch,
    level,
    setLevel,
    tag,
    setTag,
    autoRefresh,
    setAutoRefresh,
    clearLogs,
    refresh,
  } = viewModel;

  const handleCopyAll = async () => {
    if (logs.length === 0) {
      message.info("暂无可复制的日志");
      return;
    }
    const fullText = logs.map((l) => l.raw).join("\n");
    const ok = await copyToClipboard(fullText);
    if (ok) {
      message.success(`已复制 ${logs.length} 条日志`);
    } else {
      message.error("复制失败，请手动选中文本后复制");
    }
  };

  // 支持在日志区域内按下 Ctrl+A / Cmd+A 时仅全选日志区域内容，避免全屏选中
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      if (logBoxRef.current) {
        const range = document.createRange();
        range.selectNodeContents(logBoxRef.current);
        const sel = window.getSelection();
        if (sel) {
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
    }
  };

  const getLevelTag = (lvl: PluginLogItem["level"]) => {
    switch (lvl) {
      case "ERROR":
      case "CRITICAL":
        return <Tag color="error" style={{ margin: 0, fontSize: 11 }}>{lvl}</Tag>;
      case "WARNING":
        return <Tag color="warning" style={{ margin: 0, fontSize: 11 }}>WARN</Tag>;
      case "DEBUG":
        return <Tag style={{ margin: 0, fontSize: 11, color: isDark ? "#8c8c8c" : "#595959" }}>DEBUG</Tag>;
      default:
        return <Tag color="processing" style={{ margin: 0, fontSize: 11 }}>INFO</Tag>;
    }
  };

  const getTagColor = (tagStr: string) => {
    return TAG_STYLE_MAP[tagStr]?.color || "default";
  };

  return (
    <Card size="small">
      {/* 筛选与操作工具栏 */}
      <LogFilterBar
        search={search}
        level={level}
        tag={tag}
        availableTags={availableTags}
        autoRefresh={autoRefresh}
        loading={loading}
        onSearchChange={setSearch}
        onLevelChange={setLevel}
        onTagChange={setTag}
        onAutoRefreshChange={setAutoRefresh}
        onRefresh={refresh}
        onClear={clearLogs}
        onCopyAll={handleCopyAll}
      />

      {/* 控制台终端风格日志流（随亮色/暗色主题自适应） */}
      <div
        ref={logBoxRef}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        style={{
          background: isDark ? "#0d1117" : "#f8fafc",
          color: isDark ? "#e6edf3" : "#1e293b",
          borderRadius: 6,
          padding: "10px 14px",
          fontFamily:
            "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
          fontSize: 12,
          lineHeight: 1.6,
          height: "calc(100vh - 220px)",
          minHeight: 420,
          overflowY: "auto",
          border: `1px solid ${isDark ? "#303030" : "#e2e8f0"}`,
          outline: "none",
        }}
      >
        {logs.length === 0 ? (
          <div style={{ padding: "60px 0", textAlign: "center" }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span style={{ color: isDark ? "#8c8c8c" : "#64748b" }}>
                  {loading ? "正在拉取实时日志..." : "暂无匹配的插件运行日志"}
                </span>
              }
            />
          </div>
        ) : (
          logs.map((item) => {
            const isError = item.level === "ERROR" || item.level === "CRITICAL";
            const isWarn = item.level === "WARNING";

            let textColor = isDark ? "#d9d9d9" : "#1e293b";
            if (isError) textColor = isDark ? "#ff7875" : "#cf1322";
            else if (isWarn) textColor = isDark ? "#ffc069" : "#d46b08";

            return (
              <div
                key={item.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  padding: "3px 0",
                  borderBottom: `1px solid ${isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.05)"}`,
                  color: textColor,
                }}
              >
                {/* 1. 时间戳 */}
                <span
                  style={{
                    color: isDark ? "#8b949e" : "#64748b",
                    flexShrink: 0,
                    userSelect: "none",
                  }}
                >
                  {item.time_str}
                </span>

                {/* 2. 级别 */}
                <span style={{ flexShrink: 0 }}>{getLevelTag(item.level)}</span>

                {/* 3. 语义分类 Tag */}
                <Tag
                  color={getTagColor(item.tag)}
                  style={{
                    margin: 0,
                    fontSize: 10,
                    padding: "0 4px",
                    lineHeight: "18px",
                    flexShrink: 0,
                  }}
                >
                  {item.tag}
                </Tag>

                {/* 4. TraceID 交互标签（可直接点击查看详情抽屉） */}
                {item.trace_id && (
                  <a
                    onClick={() => onViewTrace(item.trace_id!)}
                    style={{
                      color: isDark ? "#58a6ff" : "#1677ff",
                      textDecoration: "underline",
                      fontSize: 11,
                      flexShrink: 0,
                    }}
                    title={`点击查看 Trace ${item.trace_id} 详情`}
                  >
                    [{item.trace_id}]
                  </a>
                )}

                {/* 5. 阶段标记（若有） */}
                {item.stage && (
                  <Tag
                    color="cyan"
                    style={{
                      margin: 0,
                      fontSize: 10,
                      padding: "0 4px",
                      lineHeight: "18px",
                      flexShrink: 0,
                    }}
                  >
                    {item.stage}
                  </Tag>
                )}

                {/* 6. 日志正文 */}
                <span
                  style={{
                    wordBreak: "break-all",
                    whiteSpace: "pre-wrap",
                    flex: 1,
                  }}
                >
                  {item.message}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* 底部条目统计 */}
      <div
        style={{
          marginTop: 8,
          display: "flex",
          justifyContent: "space-between",
          color: isDark ? "#8c8c8c" : "#64748b",
          fontSize: 11,
        }}
      >
        <span>
          当前展示：{logs.length} 条记录（内存总缓冲：{total} 条）
        </span>
        <span>
          支持按 TraceID、大模型 (LLM)、协议 (OneBot/QQOfficial) 快速过滤
        </span>
      </div>
    </Card>
  );
};
