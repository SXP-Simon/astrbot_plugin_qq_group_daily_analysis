import React from "react";
import { useTheme } from "../../../shared/lib/useTheme";

interface SpanAlertsProps {
  stageName: string;
  status: string;
  payload?: Record<string, unknown>;
}

export const SpanAlerts: React.FC<SpanAlertsProps> = ({
  stageName,
  status,
  payload,
}) => {
  const { isDark } = useTheme();

  const isFailed = status === "failed" || status === "error";

  return (
    <>
      {/* 异常提示 */}
      {isFailed && (
        <div
          style={{
            padding: "6px 10px",
            background: isDark ? "rgba(220, 38, 38, 0.1)" : "#fef2f2",
            borderLeft: "3px solid #ef4444",
            borderRadius: "0 4px 4px 0",
            color: isDark ? "#fca5a5" : "#b91c1c",
            fontSize: 11,
            marginBottom: 8,
            lineHeight: 1.5,
          }}
        >
          <span style={{ fontWeight: 600, marginRight: 6 }}>阶段执行异常：</span>
          <span className="font-mono">{String(payload?.error || "该流程执行异常中断")}</span>
        </div>
      )}

      {/* 告警/降级提示 */}
      {!isFailed && Boolean(payload?.warning) && (
        <div
          style={{
            padding: "6px 10px",
            background: isDark ? "rgba(217, 119, 6, 0.1)" : "#fffbeb",
            borderLeft: "3px solid #f59e0b",
            borderRadius: "0 4px 4px 0",
            color: isDark ? "#fbbf24" : "#92400e",
            fontSize: 11,
            marginBottom: 8,
            lineHeight: 1.5,
          }}
        >
          <span style={{ fontWeight: 600, marginRight: 6 }}>阶段告警：</span>
          <span className="font-mono">{String(payload?.warning)}</span>
        </div>
      )}

      {/* 子任务错误提示 */}
      {Array.isArray(payload?.subtask_errors) && payload.subtask_errors.length > 0 && (
        <div
          style={{
            padding: "6px 10px",
            background: isDark ? "rgba(217, 119, 6, 0.1)" : "#fffbeb",
            borderLeft: "3px solid #f59e0b",
            borderRadius: "0 4px 4px 0",
            color: isDark ? "#fbbf24" : "#92400e",
            fontSize: 11,
            marginBottom: 8,
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 2 }}>
            部分子任务调用异常：
          </div>
          {payload.subtask_errors.map((err: string, i: number) => (
            <div key={i} className="font-mono" style={{ fontSize: 10, marginTop: 1 }}>
              • {err}
            </div>
          ))}
        </div>
      )}

      {/* LLM 分析未产出提示 */}
      {stageName === "LLM_ANALYSIS" &&
        payload?.topics_count === 0 &&
        (!payload?.prompt_tokens || payload?.prompt_tokens === 0) &&
        (!Array.isArray(payload?.subtask_errors) || payload?.subtask_errors.length === 0) && (
          <div
            style={{
              padding: "6px 10px",
              background: isDark ? "rgba(217, 119, 6, 0.1)" : "#fffbeb",
              borderLeft: "3px solid #f59e0b",
              borderRadius: "0 4px 4px 0",
              color: isDark ? "#fbbf24" : "#92400e",
              fontSize: 11,
              marginBottom: 8,
              lineHeight: 1.5,
            }}
          >
            <span style={{ fontWeight: 600, marginRight: 6 }}>
              {payload?.enabled_features &&
              Object.values(payload.enabled_features).every((v) => !v)
                ? "提示："
                : "警告："}
            </span>
            <span>
              {payload?.enabled_features &&
              Object.values(payload.enabled_features).every((v) => !v)
                ? "配置项中话题、群友画像、金句和质量锐评均未开启。"
                : "模型未消耗 Token 或未能解析出任何话题/画像/金句，请检查大模型 Provider 连接与配置。"}
            </span>
          </div>
        )}
    </>
  );
};
