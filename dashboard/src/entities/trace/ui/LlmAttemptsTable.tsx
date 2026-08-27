import React from "react";
import { useTheme } from "../../../shared/lib/useTheme";

interface LlmAttemptsTableProps {
  attempts: Array<Record<string, unknown>>;
}

const AREA_NAME_MAP: Record<string, string> = {
  topics: "话题",
  user_titles: "用户称号",
  golden_quotes: "金句",
  chat_quality: "聊天质量",
  "话题分析": "话题",
  "群友画像": "用户称号",
  "群聊金句": "金句",
  "聊天质量": "聊天质量",
  group_sentiment: "情感分析",
  activity_prediction: "活跃预测",
  comic: "群漫画生成",
};

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

          const retryMatch = String(att.area || "").match(/^(.*?)#(?:schema_retry|retry)_(\d+)$/);
          const rawArea = retryMatch ? retryMatch[1] : String(att.area || "analysis");
          const areaName = AREA_NAME_MAP[rawArea] || rawArea;
          const isRetry = Boolean(retryMatch);
          const retryIdx = retryMatch ? retryMatch[2] : null;

          const badgeText = isFallback
            ? `降级 #${String(att.attempt || i + 1)}`
            : isRetry
            ? `格式纠错 #${retryIdx}`
            : `调用 #${String(att.attempt || i + 1)}`;

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
                      background: (isFallback || isRetry)
                        ? (isDark ? "rgba(217, 119, 6, 0.15)" : "#fffbeb")
                        : (isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff"),
                      color: (isFallback || isRetry)
                        ? (isDark ? "#fbbf24" : "#b45309")
                        : (isDark ? "#60a5fa" : "#1d4ed8"),
                      border: `1px solid ${
                        (isFallback || isRetry)
                          ? (isDark ? "rgba(217, 119, 6, 0.3)" : "#fde68a")
                          : (isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe")
                      }`,
                    }}
                  >
                    {badgeText}
                  </span>
                  <span style={{ fontWeight: 500, color: isDark ? "#c9d1d9" : "#1e293b" }}>
                    {areaName}
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
