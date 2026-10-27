import React from "react";
import { useTheme } from "../../../shared/lib/useTheme";
import { formatDuration } from "../../../shared/lib/formatters";
import { renderAttemptSchema } from "../model/renderAttempts";

interface RenderAttemptsTableProps {
  attempts: Array<Record<string, unknown>>;
}

export const RenderAttemptsTable: React.FC<RenderAttemptsTableProps> = ({ attempts }) => {
  const { isDark } = useTheme();

  if (!attempts || attempts.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        marginTop: 8,
        marginBottom: 8,
        border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
        borderRadius: 4,
        overflow: "hidden",
        background: isDark ? "#161b22" : "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "5px 8px",
          background: isDark ? "#21262d" : "#f8fafc",
          borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
          fontSize: 11,
        }}
      >
        <span style={{ fontWeight: 600, color: isDark ? "#c9d1d9" : "#334155" }}>
          图片渲染过程
        </span>
        <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
          共 {attempts.length} 轮策略
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        {attempts.map((record, i) => {
          const parsed = renderAttemptSchema.safeParse(record);
          if (!parsed.success) return null;
          const att = parsed.data;
          const isSuccess = att.status === "success";
          const isCancelled = att.status === "cancelled";
          const isRunning = att.status === "running";
          const hasError = !isSuccess && Boolean(att.error);
          const endpoint = att.render_service?.configured_endpoint;
          const resources = att.resource_urls;
          const details = [
            att.strategy_name,
            att.priority != null ? `优先级 ${att.priority}` : undefined,
            att.service_type === "custom" ? "自定义 T2I" : att.service_type === "astrbot" ? "AstrBot T2I" : undefined,
            att.font_mode === "local" ? "字体：本地已安装字体" : att.font_mode === "network" ? "字体：在线加载" : undefined,
            typeof att.duration_ms === "number" ? `耗时：${att.duration_ms === 0 ? "0ms" : formatDuration(att.duration_ms)}` : undefined,
            typeof att.render_timeout_ms === "number" ? `渲染超时：${formatDuration(att.render_timeout_ms)}` : undefined,
            typeof att.request_timeout_ms === "number" ? `请求等待上限：${formatDuration(att.request_timeout_ms)}` : undefined,
          ].filter(Boolean).join(" · ");

          return (
            <div
              key={i}
              style={{
                padding: "6px 8px",
                borderBottom:
                  i < attempts.length - 1
                    ? `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`
                    : "none",
                fontSize: 11,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 6,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 10,
                      padding: "1px 5px",
                      borderRadius: 3,
                      background: i > 0
                        ? (isDark ? "rgba(217, 119, 6, 0.15)" : "#fef3c7")
                        : (isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff"),
                      color: i > 0
                        ? (isDark ? "#fbbf24" : "#b45309")
                        : (isDark ? "#60a5fa" : "#1d4ed8"),
                      border: `1px solid ${
                        i > 0
                          ? (isDark ? "rgba(217, 119, 6, 0.3)" : "#fde68a")
                          : (isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe")
                      }`,
                    }}
                  >
                    {i > 0 ? "降级" : "首选"} 第 {String(att.attempt || i + 1)} 轮
                  </span>
                  <span style={{ color: isDark ? "#c9d1d9" : "#1e293b" }}>
                    格式: <b>{String(att.type || "jpeg")}</b>
                    {att.resource_environment === "Mainland" ? " | 资源环境: 内地" : att.resource_environment === "Overseas" ? " | 资源环境: 海外" : ""}
                    {att.viewport ? ` | 视口: ${String(att.viewport)}` : ""}
                  </span>
                </div>

                <span
                  style={{
                    fontSize: 10,
                    padding: "1px 5px",
                    borderRadius: 3,
                    fontWeight: 500,
                    background: isRunning ? (isDark ? "#172b4d" : "#eff6ff") : isSuccess
                      ? (isDark ? "rgba(22, 163, 74, 0.12)" : "#f0fdf4")
                      : (isDark ? "rgba(220, 38, 38, 0.12)" : "#fef2f2"),
                    color: isRunning ? (isDark ? "#60a5fa" : "#1d4ed8") : isSuccess
                      ? (isDark ? "#4ade80" : "#15803d")
                      : (isDark ? "#f87171" : "#b91c1c"),
                    border: `1px solid ${
                      isRunning ? (isDark ? "#1d4ed8" : "#bfdbfe") : isSuccess
                        ? (isDark ? "rgba(22, 163, 74, 0.25)" : "#bbf7d0")
                        : (isDark ? "rgba(220, 38, 38, 0.25)" : "#fecaca")
                    }`,
                  }}
                >
                  {isRunning ? "正在渲染" : isSuccess ? "渲染成功" : isCancelled ? "已停止" : att.status === "failed" ? "渲染失败" : "状态未知"}
                </span>
              </div>

              {details && <div style={{ marginTop: 4, overflowWrap: "anywhere", color: isDark ? "#8b949e" : "#64748b" }}>{details}</div>}
              {endpoint && <div style={{ marginTop: 4, overflowWrap: "anywhere", color: isDark ? "#8b949e" : "#64748b" }}>服务：{endpoint}</div>}
              {att.render_service?.config_lookup && <div style={{ marginTop: 4, color: isDark ? "#8b949e" : "#64748b" }}>配置来源：{att.render_service.config_lookup}</div>}
              {resources && <div style={{ marginTop: 4, overflowWrap: "anywhere", color: isDark ? "#8b949e" : "#64748b" }}>
                {resources.cdn_base_url && <div>模板资源：{resources.cdn_base_url}</div>}
                {att.font_mode !== "local" && <>
                  {resources.google_fonts && <div>字体 CSS：{resources.google_fonts}</div>}
                  {resources.gstatic && <div>字体文件：{resources.gstatic}</div>}
                </>}
              </div>}
              {hasError && (
                <div
                  className="font-mono"
                  style={{
                    marginTop: 4,
                    padding: "3px 6px",
                    background: isDark ? "rgba(220, 38, 38, 0.08)" : "#fff1f0",
                    borderLeft: "2px solid #ef4444",
                    borderRadius: "0 3px 3px 0",
                    color: isDark ? "#fca5a5" : "#cf1322",
                    fontSize: 10,
                    wordBreak: "break-all",
                    lineHeight: 1.4,
                  }}
                >
                  {String(att.error)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
