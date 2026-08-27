import React, { useRef } from "react";
import { Collapse, Button, Tooltip, Tag, message } from "antd";
import { FileTextOutlined, CopyOutlined } from "@ant-design/icons";
import { PluginLogItem, TAG_STYLE_MAP } from "../../../entities/log/model/types";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { useTheme } from "../../../shared/lib/useTheme";

interface TraceLogViewerProps {
  logs: PluginLogItem[];
}

export const TraceLogViewer: React.FC<TraceLogViewerProps> = ({ logs }) => {
  const { isDark } = useTheme();
  const logBoxRef = useRef<HTMLDivElement>(null);

  const hasLogs = logs && logs.length > 0;

  const handleCopyLogs = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!hasLogs) return;
    const text = logs
      .map(
        (l) =>
          `[${l.time_str}] [${l.level}] ${l.tag ? `[${l.tag}] ` : ""}${l.message}`
      )
      .join("\n");
    copyToClipboard(text);
    message.success("已复制任务执行日志");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "a" && hasLogs) {
      e.preventDefault();
      const text = logs
        .map(
          (l) =>
            `[${l.time_str}] [${l.level}] ${l.tag ? `[${l.tag}] ` : ""}${l.message}`
        )
        .join("\n");
      copyToClipboard(text);
      message.success("已全选并复制全部日志内容");
    }
  };

  return (
    <Collapse
      size="small"
      ghost
      defaultActiveKey={["trace-logs"]}
      items={[
        {
          key: "trace-logs",
          label: (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                width: "100%",
              }}
            >
              <span style={{ fontSize: 12, fontWeight: 600 }}>
                <FileTextOutlined style={{ marginRight: 6, color: "#1677ff" }} />
                专属执行日志 ({logs?.length || 0} 条)
              </span>
              {hasLogs && (
                <Tooltip title="一键复制当前任务专属日志 (支持 Ctrl+A 全选复制)">
                  <Button
                    size="small"
                    type="text"
                    icon={<CopyOutlined />}
                    onClick={handleCopyLogs}
                    style={{ fontSize: 11, height: 22, padding: "0 6px" }}
                  >
                    复制日志
                  </Button>
                </Tooltip>
              )}
            </div>
          ),
          children: hasLogs ? (
            <div
              ref={logBoxRef}
              tabIndex={0}
              onKeyDown={handleKeyDown}
              style={{
                background: isDark ? "#0d1117" : "#f8fafc",
                color: isDark ? "#e6edf3" : "#1e293b",
                borderRadius: 4,
                padding: "8px 10px",
                fontFamily:
                  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
                fontSize: 11,
                maxHeight: 240,
                overflowY: "auto",
                border: `1px solid ${isDark ? "#303030" : "#e2e8f0"}`,
                outline: "none",
              }}
            >
              {logs.map((l) => {
                const isError = l.level === "ERROR" || l.level === "CRITICAL";
                const isWarn = l.level === "WARNING";
                const tagColor = TAG_STYLE_MAP[l.tag]?.color || "default";

                return (
                  <div
                    key={l.id}
                    style={{
                      padding: "2px 0",
                      borderBottom: `1px solid ${
                        isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)"
                      }`,
                      color: isError
                        ? isDark ? "#ff7875" : "#cf1322"
                        : isWarn
                        ? isDark ? "#ffc069" : "#d46b08"
                        : isDark ? "#d9d9d9" : "#1e293b",
                    }}
                  >
                    <span
                      style={{
                        color: isDark ? "#8b949e" : "#64748b",
                        marginRight: 6,
                      }}
                    >
                      {l.time_str.split(" ")[1]}
                    </span>
                    <span style={{ marginRight: 6, fontWeight: 600 }}>
                      [{l.level}]
                    </span>
                    {l.tag && (
                      <Tag
                        color={tagColor}
                        style={{
                          margin: "0 6px 0 0",
                          fontSize: 10,
                          padding: "0 3px",
                          lineHeight: "16px",
                        }}
                      >
                        {l.tag}
                      </Tag>
                    )}
                    <span>{l.message}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                padding: "8px 12px",
                color: isDark ? "#8b949e" : "#64748b",
                fontSize: 12,
                fontStyle: "italic",
              }}
            >
              暂无该任务专属日志记录（或日志已随内存环形队列轮转）
            </div>
          ),
        },
      ]}
    />
  );
};
