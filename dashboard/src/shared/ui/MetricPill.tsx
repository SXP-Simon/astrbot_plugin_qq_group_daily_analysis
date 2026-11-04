import React from "react";

interface MetricPillProps {
  label: string;
  value: React.ReactNode;
  isMono?: boolean;
  status?: "default" | "success" | "error" | "warning";
  isDark: boolean;
}

export const MetricPill: React.FC<MetricPillProps> = ({
  label,
  value,
  isMono = true,
  status = "default",
  isDark,
}) => {
  let statusColor = isDark ? "#c9d1d9" : "#334155";
  let statusBg = isDark ? "#21262d" : "#f8fafc";
  let borderColor = isDark ? "#30363d" : "#e2e8f0";

  if (status === "success") {
    statusColor = isDark ? "#4ade80" : "#16a34a";
    statusBg = isDark ? "rgba(22, 163, 74, 0.12)" : "#f0fdf4";
    borderColor = isDark ? "rgba(22, 163, 74, 0.25)" : "#bbf7d0";
  } else if (status === "error") {
    statusColor = isDark ? "#f87171" : "#dc2626";
    statusBg = isDark ? "rgba(220, 38, 38, 0.12)" : "#fef2f2";
    borderColor = isDark ? "rgba(220, 38, 38, 0.25)" : "#fecaca";
  } else if (status === "warning") {
    statusColor = isDark ? "#fbbf24" : "#d97706";
    statusBg = isDark ? "rgba(217, 119, 6, 0.12)" : "#fffbeb";
    borderColor = isDark ? "rgba(217, 119, 6, 0.25)" : "#fde68a";
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 7px",
        fontSize: 11,
        borderRadius: 4,
        background: statusBg,
        border: `1px solid ${borderColor}`,
        color: statusColor,
        lineHeight: "16px",
      }}
    >
      <span style={{ color: isDark ? "#8b949e" : "#64748b" }}>{label}:</span>
      <span
        style={{
          fontWeight: 600,
          fontFamily: isMono
            ? "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace"
            : "inherit",
          color: status !== "default" ? statusColor : isDark ? "#f0f6fc" : "#0f172a",
        }}
      >
        {value}
      </span>
    </span>
  );
};

