import React from "react";
import { theme } from "antd";

interface StageMetricsBadgesProps {
  stageName: string;
  payload?: Record<string, unknown>;
}

interface MetricPillProps {
  label: string;
  value: React.ReactNode;
  isMono?: boolean;
  status?: "default" | "success" | "error" | "warning";
  isDark: boolean;
}

const MetricPill: React.FC<MetricPillProps> = ({
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
        padding: "1px 6px",
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
          color: status !== "default" ? statusColor : (isDark ? "#f0f6fc" : "#0f172a"),
        }}
      >
        {value}
      </span>
    </span>
  );
};

export const StageMetricsBadges: React.FC<StageMetricsBadgesProps> = ({
  stageName,
  payload,
}) => {
  const { token } = theme.useToken();
  const isDark = Boolean(token.colorBgBase && token.colorBgBase.toLowerCase().includes("#1"));

  if (!payload) return null;

  switch (stageName) {
    case "FETCH_MESSAGES":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {payload.fetched_count !== undefined && (
            <MetricPill isDark={isDark} label="抓取消息" value={`${Number(payload.fetched_count)} 条`} />
          )}
          {payload.days !== undefined && (
            <MetricPill isDark={isDark} label="时间跨度" value={`${Number(payload.days)} 天`} />
          )}
          {payload.max_count !== undefined && (
            <MetricPill isDark={isDark} label="最大限制" value={`${Number(payload.max_count)} 条`} />
          )}
        </div>
      );

    case "CLEAN_MESSAGES":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {payload.raw_count !== undefined && (
            <MetricPill isDark={isDark} label="原始消息" value={`${Number(payload.raw_count)} 条`} />
          )}
          {payload.cleaned_count !== undefined && (
            <MetricPill isDark={isDark} label="有效消息" value={`${Number(payload.cleaned_count)} 条`} />
          )}
          {payload.dropped_count !== undefined && (
            <MetricPill isDark={isDark} label="过滤噪音" value={`${Number(payload.dropped_count)} 条`} />
          )}
          {payload.retention_rate !== undefined && (
            <MetricPill
              isDark={isDark}
              label="留存率"
              value={`${Number(payload.retention_rate)}%`}
              status={Number(payload.retention_rate) > 40 ? "success" : "default"}
            />
          )}
        </div>
      );

    case "STATS_ANALYSIS":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {payload.message_count !== undefined && (
            <MetricPill isDark={isDark} label="消息总数" value={`${Number(payload.message_count)} 条`} />
          )}
          {payload.character_count !== undefined && (
            <MetricPill isDark={isDark} label="字符总数" value={`${Number(payload.character_count)} 字`} />
          )}
          {payload.participant_count !== undefined && (
            <MetricPill isDark={isDark} label="发言人数" value={`${Number(payload.participant_count)} 人`} />
          )}
          {Boolean(payload.most_active_period) && (
            <MetricPill isDark={isDark} label="高峰时段" value={String(payload.most_active_period)} isMono={false} />
          )}
          {payload.emoji_count !== undefined && (
            <MetricPill isDark={isDark} label="表情总数" value={`${Number(payload.emoji_count)} 个`} />
          )}
        </div>
      );

    case "CHECKPOINT_RESTORE":
      return (
        <div style={{ marginBottom: 6 }}>
          <MetricPill isDark={isDark} label="快照恢复" value="已恢复前置清洗与基础统计快照，免重复拉取" isMono={false} status="success" />
        </div>
      );

    case "SAVE_SUMMARY":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.date) && (
            <MetricPill isDark={isDark} label="归档日期" value={String(payload.date)} isMono={false} />
          )}
          {payload.topics_persisted !== undefined && (
            <MetricPill isDark={isDark} label="话题持久化" value={`${Number(payload.topics_persisted)} 个`} />
          )}
          {payload.titles_persisted !== undefined && (
            <MetricPill isDark={isDark} label="称号持久化" value={`${Number(payload.titles_persisted)} 个`} />
          )}
          {Boolean(payload.checkpoint_saved) && (
            <MetricPill isDark={isDark} label="快照存储" value="成功 (可免 Token 重绘)" isMono={false} status="success" />
          )}
        </div>
      );

    case "RENDER_REPORT":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.format) && (
            <MetricPill isDark={isDark} label="格式" value={String(payload.format)} isMono={false} />
          )}
          {Boolean(payload.template) && (
            <MetricPill isDark={isDark} label="主题" value={String(payload.template)} isMono={false} />
          )}
          {payload.image_bytes !== undefined && Number(payload.image_bytes) > 0 && (
            <MetricPill isDark={isDark} label="体积" value={`${(Number(payload.image_bytes) / 1024).toFixed(1)} KB`} />
          )}
          {payload.render_attempt !== undefined && (
            <MetricPill isDark={isDark} label="轮次" value={`第 ${Number(payload.render_attempt)} 轮`} />
          )}
          {Boolean(payload.viewport) && (
            <MetricPill isDark={isDark} label="视口" value={String(payload.viewport)} />
          )}
          {payload.topics_rendered !== undefined && (
            <MetricPill isDark={isDark} label="话题渲染" value={`${Number(payload.topics_rendered)} 个`} />
          )}
          {payload.titles_rendered !== undefined && (
            <MetricPill isDark={isDark} label="称号渲染" value={`${Number(payload.titles_rendered)} 个`} />
          )}
          {payload.avatars_processed !== undefined && Number(payload.avatars_processed) > 0 && (
            <MetricPill isDark={isDark} label="头像解析" value={`${Number(payload.avatars_processed)} 个`} />
          )}
          {Boolean(payload.hide_user_names) && (
            <MetricPill isDark={isDark} label="隐私保护" value="匿名模式" isMono={false} />
          )}
        </div>
      );

    case "DISPATCH_REPORT":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.platform) && (
            <MetricPill isDark={isDark} label="目标平台" value={String(payload.platform)} isMono={false} />
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <MetricPill
              isDark={isDark}
              label="分发格式"
              value={Array.isArray(payload.formats) ? (payload.formats as string[]).join(", ") : String(payload.format || payload.formats)}
              isMono={false}
            />
          )}
          {payload.success !== undefined && (
            <MetricPill
              isDark={isDark}
              label="分发状态"
              value={payload.success ? "完成" : "失败/回退"}
              isMono={false}
              status={payload.success ? "success" : "error"}
            />
          )}
          {payload.image_sent !== undefined && (
            <MetricPill
              isDark={isDark}
              label="图片"
              value={payload.image_sent ? "已发送" : "未发送"}
              isMono={false}
              status={payload.image_sent ? "success" : "default"}
            />
          )}
          {payload.html_sent !== undefined && (
            <MetricPill
              isDark={isDark}
              label="HTML"
              value={payload.html_sent ? "已发送" : "未发送"}
              isMono={false}
              status={payload.html_sent ? "success" : "default"}
            />
          )}
        </div>
      );

    case "COMIC_STORYBOARD":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.character_name) && (
            <MetricPill isDark={isDark} label="角色方案" value={String(payload.character_name)} isMono={false} />
          )}
          {payload.storyboards_count !== undefined && (
            <MetricPill isDark={isDark} label="分镜数" value={`${Number(payload.storyboards_count)} 格`} />
          )}
          {payload.total_tokens !== undefined && Number(payload.total_tokens) > 0 && (
            <MetricPill isDark={isDark} label="Token" value={Number(payload.total_tokens).toLocaleString()} />
          )}
        </div>
      );

    case "COMIC_DRAWING":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.backend) && (
            <MetricPill isDark={isDark} label="绘图后端" value={String(payload.backend)} isMono={false} />
          )}
          {payload.reference_images_count !== undefined && (
            <MetricPill isDark={isDark} label="参考图" value={`${Number(payload.reference_images_count)} 张`} />
          )}
          {payload.success !== undefined && (
            <MetricPill
              isDark={isDark}
              label="出图状态"
              value={payload.success ? "成功" : "失败"}
              isMono={false}
              status={payload.success ? "success" : "error"}
            />
          )}
        </div>
      );

    case "LLM_ANALYSIS":
      if (
        payload.enabled_features &&
        typeof payload.enabled_features === "object"
      ) {
        const feats = payload.enabled_features as Record<string, boolean>;
        return (
          <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
            <MetricPill
              isDark={isDark}
              label="话题分析"
              value={feats.topics !== false ? "开启" : "关闭"}
              isMono={false}
              status={feats.topics !== false ? "success" : "default"}
            />
            <MetricPill
              isDark={isDark}
              label="群友画像"
              value={feats.user_titles !== false ? "开启" : "关闭"}
              isMono={false}
              status={feats.user_titles !== false ? "success" : "default"}
            />
            <MetricPill
              isDark={isDark}
              label="精彩金句"
              value={feats.golden_quotes !== false ? "开启" : "关闭"}
              isMono={false}
              status={feats.golden_quotes !== false ? "success" : "default"}
            />
            <MetricPill
              isDark={isDark}
              label="质量锐评"
              value={feats.chat_quality !== false ? "开启" : "关闭"}
              isMono={false}
              status={feats.chat_quality !== false ? "success" : "default"}
            />
          </div>
        );
      }
      return null;

    default:
      return null;
  }
};
