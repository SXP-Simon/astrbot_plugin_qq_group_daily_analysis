import React from "react";
import { useTheme } from "../../../shared/lib/useTheme";

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

export const StageMetricsBadges: React.FC<StageMetricsBadgesProps> = ({
  stageName,
  payload,
}) => {
  const { isDark } = useTheme();

  if (!payload) return null;

  const renderMemoryPill = () => {
    if (payload.delta_memory_mb !== undefined && payload.delta_memory_mb !== null) {
      const delta = Number(payload.delta_memory_mb);
      const isIncrease = delta > 0;
      return (
        <MetricPill
          isDark={isDark}
          label="内存RSS"
          value={`${isIncrease ? `+${delta.toFixed(1)}` : delta.toFixed(1)} MB`}
          status={delta > 15 ? "warning" : "default"}
        />
      );
    }
    return null;
  };

  const normStage = (stageName || "").toUpperCase().replace(/-/g, "_");

  switch (normStage) {
    case "FETCH_MESSAGES":
    case "DATA_FETCHING":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {(payload.fetched_count !== undefined || payload.raw_messages !== undefined) && (
            <MetricPill
              isDark={isDark}
              label="拉取消息"
              value={`${Number(payload.fetched_count ?? payload.raw_messages).toLocaleString()} 条`}
            />
          )}
          {(payload.retained !== undefined || payload.cleaned_count !== undefined) && (
            <MetricPill
              isDark={isDark}
              label="留存有效"
              value={`${Number(payload.retained ?? payload.cleaned_count).toLocaleString()} 条`}
              status="success"
            />
          )}
          {payload.max_count !== undefined && (
            <MetricPill isDark={isDark} label="最大限制" value={`${Number(payload.max_count)} 条`} />
          )}
          {payload.raw_data_size_kb !== undefined && Number(payload.raw_data_size_kb) > 0 && (
            <MetricPill isDark={isDark} label="原始体量" value={`${Number(payload.raw_data_size_kb)} KB`} />
          )}
          {payload.batch_chunks !== undefined && (
            <MetricPill isDark={isDark} label="分块批次" value={`${Number(payload.batch_chunks)} 块`} />
          )}
          {payload.days !== undefined && (
            <MetricPill isDark={isDark} label="时间跨度" value={`${Number(payload.days)} 天`} />
          )}
          {Boolean(payload.platform || payload.source) && (
            <MetricPill isDark={isDark} label="平台源" value={String(payload.platform || payload.source)} isMono={false} />
          )}
          {Boolean(payload.reason) && (
            <MetricPill isDark={isDark} label="跳过原因" value={String(payload.reason)} isMono={false} status="warning" />
          )}
          {renderMemoryPill()}
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
          {payload.cleaning_speed_mps !== undefined && Number(payload.cleaning_speed_mps) > 0 && (
            <MetricPill isDark={isDark} label="清洗速度" value={`${Number(payload.cleaning_speed_mps).toLocaleString()} 条/秒`} />
          )}
          {payload.cleaned_data_size_kb !== undefined && Number(payload.cleaned_data_size_kb) > 0 && (
            <MetricPill isDark={isDark} label="净化体量" value={`${Number(payload.cleaned_data_size_kb)} KB`} />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "INCREMENTAL_AGGREGATION":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {payload.aggregated_batches !== undefined && (
            <MetricPill isDark={isDark} label="聚合批次" value={`${Number(payload.aggregated_batches)} 批`} status="success" />
          )}
          {payload.keywords_extracted !== undefined && (
            <MetricPill isDark={isDark} label="关键词提炼" value={`${Number(payload.keywords_extracted)} 个`} />
          )}
          {renderMemoryPill()}
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
          {payload.emoji_count !== undefined && (
            <MetricPill isDark={isDark} label="表情总数" value={`${Number(payload.emoji_count)} 个`} />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "CHECKPOINT_RESTORE":
    case "CRASH_RECOVERY":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          <MetricPill
            isDark={isDark}
            label="快照恢复"
            value={payload.resumed_from ? `从快照 [${payload.resumed_from}] 恢复执行` : "已成功从前置快照恢复"}
            isMono={false}
            status="success"
          />
          {renderMemoryPill()}
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
          {Boolean(payload.checkpoint_saved) && (
            <MetricPill isDark={isDark} label="快照存储" value="成功 (可免 Token 重绘)" isMono={false} status="success" />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "RENDER_REPORT":
    case "REPORT_RENDERING":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.template) && (
            <MetricPill isDark={isDark} label="主题模板" value={String(payload.template)} isMono={false} status="success" />
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <MetricPill
              isDark={isDark}
              label="输出格式"
              value={Array.isArray(payload.formats) ? (payload.formats as string[]).join(", ") : String(payload.format || payload.formats)}
              isMono={false}
            />
          )}
          {(payload.width !== undefined || payload.height !== undefined || payload.resolution !== undefined || payload.dimensions !== undefined) && (
            <MetricPill
              isDark={isDark}
              label="渲染分辨率"
              value={String(payload.dimensions || payload.resolution || `${payload.width}x${payload.height}`)}
            />
          )}
          {payload.html_size_kb !== undefined && Number(payload.html_size_kb) > 0 && (
            <MetricPill isDark={isDark} label="HTML源码" value={`${Number(payload.html_size_kb)} KB`} />
          )}
          {payload.image_bytes !== undefined && Number(payload.image_bytes) > 0 && (
            <MetricPill isDark={isDark} label="图片体积" value={`${(Number(payload.image_bytes) / 1024).toFixed(1)} KB`} />
          )}
          {payload.template_render_ms !== undefined && Number(payload.template_render_ms) > 0 && (
            <MetricPill isDark={isDark} label="模板耗时" value={`${Number(payload.template_render_ms)} ms`} />
          )}
          {payload.t2i_render_ms !== undefined && Number(payload.t2i_render_ms) > 0 && (
            <MetricPill isDark={isDark} label="T2I耗时" value={`${Number(payload.t2i_render_ms)} ms`} />
          )}
          {Boolean(payload.t2i_engine) && (
            <MetricPill isDark={isDark} label="渲染引擎" value={String(payload.t2i_engine)} isMono={false} />
          )}
          {payload.render_attempt !== undefined && (
            <MetricPill isDark={isDark} label="渲染轮次" value={`第 ${Number(payload.render_attempt)} 轮`} />
          )}
          {Boolean(payload.hide_user_names) && (
            <MetricPill isDark={isDark} label="隐私保护" value="匿名模式" isMono={false} />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "DISPATCH_REPORT":
    case "MESSAGE_DISPATCH":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.target_group || payload.target_channel) && (
            <MetricPill isDark={isDark} label="目标群/频道" value={String(payload.target_group || payload.target_channel)} />
          )}
          {Boolean(payload.platform) && (
            <MetricPill isDark={isDark} label="目标平台" value={String(payload.platform)} isMono={false} />
          )}
          {Boolean(payload.transmission_mode) && (
            <MetricPill
              isDark={isDark}
              label="传输协议"
              value={payload.transmission_mode === "base64" ? "Base64 数据流" : "本地物理路径"}
              isMono={false}
            />
          )}
          {Boolean(payload.bloat_ratio) && (
            <MetricPill
              isDark={isDark}
              label="数据膨胀"
              value={String(payload.bloat_ratio)}
              status="warning"
            />
          )}
          {payload.base64_payload_kb !== undefined && Number(payload.base64_payload_kb) > 0 && (
            <MetricPill isDark={isDark} label="传输载荷" value={`${Number(payload.base64_payload_kb)} KB`} />
          )}
          {payload.dispatch_api_ms !== undefined && Number(payload.dispatch_api_ms) > 0 && (
            <MetricPill isDark={isDark} label="API耗时" value={`${Number(payload.dispatch_api_ms)} ms`} />
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <MetricPill
              isDark={isDark}
              label="分发格式"
              value={Array.isArray(payload.formats) ? (payload.formats as string[]).join(", ") : String(payload.format || payload.formats)}
              isMono={false}
            />
          )}
          {Boolean(payload.album_uploaded) && (
            <MetricPill isDark={isDark} label="QQ群相册" value="已同步上传" isMono={false} status="success" />
          )}
          {Boolean(payload.html_url_generated) && (
            <MetricPill isDark={isDark} label="在线交互报告" value="已生成 URL" isMono={false} status="success" />
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
          {renderMemoryPill()}
        </div>
      );

    case "COMIC_STORYBOARD":
    case "COMIC_DRAWING":
    case "COMIC_GENERATION":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {(payload.panels !== undefined || payload.storyboards_count !== undefined) && (
            <MetricPill
              isDark={isDark}
              label="分镜格数"
              value={`${Number(payload.panels ?? payload.storyboards_count)} 格`}
              status="success"
            />
          )}
          {Boolean(payload.engine || payload.backend) && (
            <MetricPill isDark={isDark} label="生图引擎" value={String(payload.engine || payload.backend)} isMono={false} />
          )}
          {Boolean(payload.style || payload.character_name) && (
            <MetricPill isDark={isDark} label="风格/方案" value={String(payload.style || payload.character_name)} isMono={false} />
          )}
          {Boolean(payload.resolution) && (
            <MetricPill isDark={isDark} label="生图分辨率" value={String(payload.resolution)} />
          )}
          {payload.reference_images_count !== undefined && (
            <MetricPill isDark={isDark} label="参考图" value={`${Number(payload.reference_images_count)} 张`} />
          )}
          {payload.total_tokens !== undefined && Number(payload.total_tokens) > 0 && (
            <MetricPill isDark={isDark} label="Token" value={Number(payload.total_tokens).toLocaleString()} />
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
          {Boolean(payload.warning) && (
            <MetricPill isDark={isDark} label="降级预警" value={String(payload.warning)} isMono={false} status="warning" />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "LLM_ANALYSIS":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Boolean(payload.provider) && (
            <MetricPill isDark={isDark} label="推理服务" value={String(payload.provider)} isMono={false} status="success" />
          )}
          {Boolean(payload.model) && String(payload.model) !== String(payload.provider) && (
            <MetricPill isDark={isDark} label="模型版本" value={String(payload.model)} isMono={false} />
          )}
          {(payload.tokens !== undefined || payload.total_tokens !== undefined) && (
            <MetricPill
              isDark={isDark}
              label="模型消耗"
              value={`${Number(payload.tokens ?? payload.total_tokens).toLocaleString()} Tokens`}
              status="success"
            />
          )}
          {payload.cache_hits !== undefined && Number(payload.cache_hits) > 0 && (
            <MetricPill
              isDark={isDark}
              label="Prompt 缓存命中"
              value={`${Number(payload.cache_hits).toLocaleString()} Tokens`}
              status="success"
            />
          )}
          {payload.temperature !== undefined && (
            <MetricPill isDark={isDark} label="发散度 (temp)" value={String(payload.temperature)} />
          )}
          {Boolean(payload.enabled_features && typeof payload.enabled_features === "object") && (
            <>
              {(payload.enabled_features as Record<string, boolean>).topics !== false && (
                <MetricPill isDark={isDark} label="话题分析" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).user_titles !== false && (
                <MetricPill isDark={isDark} label="群友画像" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).golden_quotes !== false && (
                <MetricPill isDark={isDark} label="精彩金句" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).chat_quality !== false && (
                <MetricPill isDark={isDark} label="质量锐评" value="开启" isMono={false} status="success" />
              )}
            </>
          )}
          {renderMemoryPill()}
        </div>
      );

    default:
      return null;
  }
};
