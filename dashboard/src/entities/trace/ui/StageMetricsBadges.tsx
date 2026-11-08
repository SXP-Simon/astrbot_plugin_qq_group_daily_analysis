import React from "react";
import { StageMetric } from "./StageMetric";
import { RenderingStageMetrics } from "./RenderingStageMetrics";

interface StageMetricsBadgesProps {
  stageName: string;
  payload?: Record<string, unknown>;
}

export const StageMetricsBadges: React.FC<StageMetricsBadgesProps> = ({ stageName, payload }) => {
  if (!payload) return null;

  const renderMemoryPill = () => {
    if (payload.delta_memory_mb !== undefined && payload.delta_memory_mb !== null) {
      const delta = Number(payload.delta_memory_mb);
      if (!Number.isFinite(delta)) return null;
      const isIncrease = delta > 0;
      return (
        <span title="宿主在本阶段结束与开始时的 RSS 差值，不包含隔离的 Typst 子进程，也不是阶段内存峰值。">
          <StageMetric
            label="宿主 RSS 净变化"
            value={`${isIncrease ? `+${delta.toFixed(1)}` : delta.toFixed(1)} MiB`}
            status={delta > 15 ? "warning" : "default"}
          />
        </span>
      );
    }
    return null;
  };

  const normStage = (stageName || "").toUpperCase().replace(/-/g, "_");

  if (normStage.startsWith("TYPST_") || normStage.startsWith("IMAGE_")) {
    return <RenderingStageMetrics payload={payload}>{renderMemoryPill()}</RenderingStageMetrics>;
  }

  switch (normStage) {
    case "FETCH_MESSAGES":
    case "DATA_FETCHING":
      return (
        <div className="stage-metrics-grid">
          {(payload.fetched_count !== undefined || payload.raw_messages !== undefined) && (
            <StageMetric
              label="拉取消息"
              value={`${Number(payload.fetched_count ?? payload.raw_messages).toLocaleString()} 条`}
            />
          )}
          {(payload.retained !== undefined || payload.cleaned_count !== undefined) && (
            <StageMetric
              label="留存有效"
              value={`${Number(payload.retained ?? payload.cleaned_count).toLocaleString()} 条`}
              status="success"
            />
          )}
          {payload.max_count !== undefined && (
            <StageMetric label="最大限制" value={`${Number(payload.max_count)} 条`} />
          )}
          {payload.raw_data_size_kb !== undefined && Number(payload.raw_data_size_kb) > 0 && (
            <StageMetric label="原始体量" value={`${Number(payload.raw_data_size_kb)} KB`} />
          )}
          {payload.batch_chunks !== undefined && (
            <StageMetric label="分块批次" value={`${Number(payload.batch_chunks)} 块`} />
          )}
          {payload.days !== undefined && (
            <StageMetric label="时间跨度" value={`${Number(payload.days)} 天`} />
          )}
          {Boolean(payload.platform || payload.source) && (
            <StageMetric
              label="平台源"
              value={String(payload.platform || payload.source)}
              isMono={false}
            />
          )}
          {Boolean(payload.reason) && (
            <StageMetric
              label="跳过原因"
              value={String(payload.reason)}
              isMono={false}
              status="warning"
            />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "CLEAN_MESSAGES":
      return (
        <div className="stage-metrics-grid">
          {payload.raw_count !== undefined && (
            <StageMetric label="原始消息" value={`${Number(payload.raw_count)} 条`} />
          )}
          {payload.cleaned_count !== undefined && (
            <StageMetric label="有效消息" value={`${Number(payload.cleaned_count)} 条`} />
          )}
          {payload.dropped_count !== undefined && (
            <StageMetric label="过滤噪音" value={`${Number(payload.dropped_count)} 条`} />
          )}
          {payload.retention_rate !== undefined && (
            <StageMetric
              label="留存率"
              value={`${Number(payload.retention_rate)}%`}
              status={Number(payload.retention_rate) > 40 ? "success" : "default"}
            />
          )}
          {payload.cleaning_speed_mps !== undefined && Number(payload.cleaning_speed_mps) > 0 && (
            <StageMetric
              label="清洗速度"
              value={`${Number(payload.cleaning_speed_mps).toLocaleString()} 条/秒`}
            />
          )}
          {payload.cleaned_data_size_kb !== undefined &&
            Number(payload.cleaned_data_size_kb) > 0 && (
              <StageMetric label="净化体量" value={`${Number(payload.cleaned_data_size_kb)} KB`} />
            )}
          {renderMemoryPill()}
        </div>
      );

    case "INCREMENTAL_AGGREGATION":
      return (
        <div className="stage-metrics-grid">
          {payload.aggregated_batches !== undefined && (
            <StageMetric
              label="聚合批次"
              value={`${Number(payload.aggregated_batches)} 批`}
              status="success"
            />
          )}
          {payload.keywords_extracted !== undefined && (
            <StageMetric label="关键词提炼" value={`${Number(payload.keywords_extracted)} 个`} />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "STATS_ANALYSIS":
      return (
        <div className="stage-metrics-grid">
          {payload.message_count !== undefined && (
            <StageMetric label="消息总数" value={`${Number(payload.message_count)} 条`} />
          )}
          {payload.character_count !== undefined && (
            <StageMetric label="字符总数" value={`${Number(payload.character_count)} 字`} />
          )}
          {payload.participant_count !== undefined && (
            <StageMetric label="发言人数" value={`${Number(payload.participant_count)} 人`} />
          )}
          {payload.emoji_count !== undefined && (
            <StageMetric label="表情总数" value={`${Number(payload.emoji_count)} 个`} />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "CHECKPOINT_RESTORE":
    case "CRASH_RECOVERY":
      return (
        <div className="stage-metrics-grid">
          <StageMetric
            label="快照恢复"
            value={
              payload.resumed_from
                ? `从快照 [${payload.resumed_from}] 恢复执行`
                : "已成功从前置快照恢复"
            }
            isMono={false}
            status="success"
          />
          {renderMemoryPill()}
        </div>
      );

    case "SAVE_SUMMARY":
      return (
        <div className="stage-metrics-grid">
          {Boolean(payload.date) && (
            <StageMetric label="归档日期" value={String(payload.date)} isMono={false} />
          )}
          {payload.topics_persisted !== undefined && (
            <StageMetric label="话题持久化" value={`${Number(payload.topics_persisted)} 个`} />
          )}
          {Boolean(payload.checkpoint_saved) && (
            <StageMetric
              label="快照存储"
              value="成功 (可免 Token 重绘)"
              isMono={false}
              status="success"
            />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "RENDER_REPORT":
    case "REPORT_RENDERING":
      return (
        <div className="stage-metrics-grid">
          {Boolean(payload.template) && (
            <StageMetric
              label="主题模板"
              value={String(payload.template)}
              isMono={false}
              status="success"
            />
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <StageMetric
              label="输出格式"
              value={
                Array.isArray(payload.formats)
                  ? (payload.formats as string[]).join(", ")
                  : String(payload.format || payload.formats)
              }
              isMono={false}
            />
          )}
          {(payload.width !== undefined ||
            payload.height !== undefined ||
            payload.resolution !== undefined ||
            payload.dimensions !== undefined) && (
            <StageMetric
              label="渲染分辨率"
              value={String(
                payload.dimensions || payload.resolution || `${payload.width}x${payload.height}`,
              )}
            />
          )}
          {payload.html_size_kb !== undefined && Number(payload.html_size_kb) > 0 && (
            <StageMetric label="HTML源码" value={`${Number(payload.html_size_kb)} KB`} />
          )}
          {payload.image_bytes !== undefined && Number(payload.image_bytes) > 0 && (
            <StageMetric
              label="图片体积"
              value={`${(Number(payload.image_bytes) / 1024).toFixed(1)} KB`}
            />
          )}
          {payload.template_render_ms !== undefined && Number(payload.template_render_ms) > 0 && (
            <StageMetric label="模板耗时" value={`${Number(payload.template_render_ms)} ms`} />
          )}
          {payload.t2i_render_ms !== undefined && Number(payload.t2i_render_ms) > 0 && (
            <StageMetric label="T2I耗时" value={`${Number(payload.t2i_render_ms)} ms`} />
          )}
          {Boolean(payload.t2i_engine) && (
            <StageMetric label="渲染引擎" value={String(payload.t2i_engine)} isMono={false} />
          )}
          {payload.render_attempt !== undefined && (
            <StageMetric label="渲染轮次" value={`第 ${Number(payload.render_attempt)} 轮`} />
          )}
          {Boolean(payload.hide_user_names) && (
            <StageMetric label="隐私保护" value="匿名模式" isMono={false} />
          )}
          {typeof payload.typst_peak_rss_mb === "number" &&
            Number.isFinite(payload.typst_peak_rss_mb) && (
              <RenderingStageMetrics
                payload={{
                  typst_peak_rss_mb: payload.typst_peak_rss_mb,
                  typst_peak_delta_mb: payload.typst_peak_delta_mb,
                  typst_rss_source: payload.typst_rss_source,
                  typst_metrics_partial: payload.typst_metrics_partial,
                }}
              />
            )}
          {renderMemoryPill()}
        </div>
      );

    case "DISPATCH_REPORT":
    case "MESSAGE_DISPATCH":
      return (
        <div className="stage-metrics-grid">
          {Boolean(payload.target_group || payload.target_channel) && (
            <StageMetric
              label="目标群/频道"
              value={String(payload.target_group || payload.target_channel)}
            />
          )}
          {Boolean(payload.platform) && (
            <StageMetric label="目标平台" value={String(payload.platform)} isMono={false} />
          )}
          {Boolean(payload.transmission_mode) && (
            <StageMetric
              label="传输协议"
              value={payload.transmission_mode === "base64" ? "Base64 数据流" : "本地物理路径"}
              isMono={false}
            />
          )}
          {Boolean(payload.bloat_ratio) && (
            <StageMetric label="数据膨胀" value={String(payload.bloat_ratio)} status="warning" />
          )}
          {payload.base64_payload_kb !== undefined && Number(payload.base64_payload_kb) > 0 && (
            <StageMetric label="传输载荷" value={`${Number(payload.base64_payload_kb)} KB`} />
          )}
          {payload.dispatch_api_ms !== undefined && Number(payload.dispatch_api_ms) > 0 && (
            <StageMetric label="API耗时" value={`${Number(payload.dispatch_api_ms)} ms`} />
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <StageMetric
              label="分发格式"
              value={
                Array.isArray(payload.formats)
                  ? (payload.formats as string[]).join(", ")
                  : String(payload.format || payload.formats)
              }
              isMono={false}
            />
          )}
          {Boolean(payload.album_uploaded) && (
            <StageMetric label="QQ群相册" value="已同步上传" isMono={false} status="success" />
          )}
          {Boolean(payload.html_url_generated) && (
            <StageMetric label="在线交互报告" value="已生成 URL" isMono={false} status="success" />
          )}
          {payload.success !== undefined && (
            <StageMetric
              label="分发状态"
              value={payload.success ? "完成" : "失败/回退"}
              isMono={false}
              status={payload.success ? "success" : "error"}
            />
          )}
          {payload.image_sent !== undefined && (
            <StageMetric
              label="图片"
              value={payload.image_sent ? "已发送" : "未发送"}
              isMono={false}
              status={payload.image_sent ? "success" : "default"}
            />
          )}
          {payload.html_sent !== undefined && (
            <StageMetric
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
        <div className="stage-metrics-grid">
          {(payload.panels !== undefined || payload.storyboards_count !== undefined) && (
            <StageMetric
              label="分镜格数"
              value={`${Number(payload.panels ?? payload.storyboards_count)} 格`}
              status="success"
            />
          )}
          {Boolean(payload.engine || payload.backend) && (
            <StageMetric
              label="生图引擎"
              value={String(payload.engine || payload.backend)}
              isMono={false}
            />
          )}
          {Boolean(payload.style || payload.character_name) && (
            <StageMetric
              label="风格/方案"
              value={String(payload.style || payload.character_name)}
              isMono={false}
            />
          )}
          {Boolean(payload.resolution) && (
            <StageMetric label="生图分辨率" value={String(payload.resolution)} />
          )}
          {payload.reference_images_count !== undefined && (
            <StageMetric label="参考图" value={`${Number(payload.reference_images_count)} 张`} />
          )}
          {payload.total_tokens !== undefined && Number(payload.total_tokens) > 0 && (
            <StageMetric label="Token" value={Number(payload.total_tokens).toLocaleString()} />
          )}
          {payload.success !== undefined && (
            <StageMetric
              label="出图状态"
              value={payload.success ? "成功" : "失败"}
              isMono={false}
              status={payload.success ? "success" : "error"}
            />
          )}
          {Boolean(payload.warning) && (
            <StageMetric
              label="降级预警"
              value={String(payload.warning)}
              isMono={false}
              status="warning"
            />
          )}
          {renderMemoryPill()}
        </div>
      );

    case "LLM_ANALYSIS":
      return (
        <div className="stage-metrics-grid">
          {Boolean(payload.provider) && (
            <StageMetric
              label="推理服务"
              value={String(payload.provider)}
              isMono={false}
              status="success"
            />
          )}
          {Boolean(payload.model) && String(payload.model) !== String(payload.provider) && (
            <StageMetric label="模型版本" value={String(payload.model)} isMono={false} />
          )}
          {(payload.tokens !== undefined || payload.total_tokens !== undefined) && (
            <StageMetric
              label="模型消耗"
              value={`${Number(payload.tokens ?? payload.total_tokens).toLocaleString()} Tokens`}
              status="success"
            />
          )}
          {payload.cache_hits !== undefined && Number(payload.cache_hits) > 0 && (
            <StageMetric
              label="Prompt 缓存命中"
              value={`${Number(payload.cache_hits).toLocaleString()} Tokens`}
              status="success"
            />
          )}
          {payload.temperature !== undefined && (
            <StageMetric label="发散度 (temp)" value={String(payload.temperature)} />
          )}
          {Boolean(payload.enabled_features && typeof payload.enabled_features === "object") && (
            <>
              {(payload.enabled_features as Record<string, boolean>).topics !== false && (
                <StageMetric label="话题分析" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).user_titles !== false && (
                <StageMetric label="群友画像" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).golden_quotes !== false && (
                <StageMetric label="精彩金句" value="开启" isMono={false} status="success" />
              )}
              {(payload.enabled_features as Record<string, boolean>).chat_quality !== false && (
                <StageMetric label="质量锐评" value="开启" isMono={false} status="success" />
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
