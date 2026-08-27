import React from "react";
import { useTheme } from "../../../shared/lib/useTheme";

interface LlmAttemptsTableProps {
  attempts: Array<Record<string, unknown>>;
}

export const LlmAttemptsTable: React.FC<LlmAttemptsTableProps> = ({ attempts }) => {
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
          大模型调用与重试链路
        </span>
        <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
          共 {attempts.length} 次请求
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        {attempts.map((att: Record<string, unknown>, i: number) => {
          const isSuccess = att.status === "success";
          const isFallback = Boolean(att.is_fallback);
          const hasError = !isSuccess && Boolean(att.error);

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
                      background: isFallback
                        ? (isDark ? "rgba(217, 119, 6, 0.15)" : "#fef3c7")
                        : (isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff"),
                      color: isFallback
                        ? (isDark ? "#fbbf24" : "#b45309")
                        : (isDark ? "#60a5fa" : "#1d4ed8"),
                      border: `1px solid ${
                        isFallback
                          ? (isDark ? "rgba(217, 119, 6, 0.3)" : "#fde68a")
                          : (isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe")
                      }`,
                    }}
                  >
                    {isFallback ? "降级" : "调用"} #{String(att.attempt || i + 1)}
                  </span>
                  <span style={{ fontWeight: 500, color: isDark ? "#c9d1d9" : "#1e293b" }}>
                    {String(att.area || "analysis")}
                  </span>
                  <span className="font-mono" style={{ color: isDark ? "#8b949e" : "#64748b", fontSize: 11 }}>
                    {String(att.provider_id || "default")}
                    {att.model &&
                    String(att.model) !== String(att.provider_id) &&
                    !String(att.provider_id || "").includes(String(att.model))
                      ? ` / ${String(att.model)}`
                      : ""}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {att.duration_ms !== undefined && (
                    <span className="font-mono" style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b" }}>
                      {Number(att.duration_ms) < 1000
                        ? `${att.duration_ms}ms`
                        : `${(Number(att.duration_ms) / 1000).toFixed(1)}s`}
                    </span>
                  )}
                  <span
                    style={{
                      fontSize: 10,
                      padding: "1px 5px",
                      borderRadius: 3,
                      fontWeight: 500,
                      background: isSuccess
                        ? (isDark ? "rgba(22, 163, 74, 0.12)" : "#f0fdf4")
                        : (isDark ? "rgba(220, 38, 38, 0.12)" : "#fef2f2"),
                      color: isSuccess
                        ? (isDark ? "#4ade80" : "#15803d")
                        : (isDark ? "#f87171" : "#b91c1c"),
                      border: `1px solid ${
                        isSuccess
                          ? (isDark ? "rgba(22, 163, 74, 0.25)" : "#bbf7d0")
                          : (isDark ? "rgba(220, 38, 38, 0.25)" : "#fecaca")
                      }`,
                    }}
                  >
                    {isSuccess ? "成功" : "失败"}
                  </span>
                </div>
              </div>

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
