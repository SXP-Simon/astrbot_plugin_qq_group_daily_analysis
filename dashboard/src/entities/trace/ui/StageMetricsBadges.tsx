import React from "react";
import { Tag } from "antd";

interface StageMetricsBadgesProps {
  stageName: string;
  payload?: Record<string, unknown>;
}

export const StageMetricsBadges: React.FC<StageMetricsBadgesProps> = ({
  stageName,
  payload,
}) => {
  if (!payload) return null;

  switch (stageName) {
    case "FETCH_MESSAGES":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {payload.fetched_count !== undefined && (
            <Tag color="blue">拉取消息: {Number(payload.fetched_count)} 条</Tag>
          )}
          {payload.days !== undefined && (
            <Tag color="cyan">时间跨度: {Number(payload.days)} 天</Tag>
          )}
          {payload.max_count !== undefined && (
            <Tag color="default">最大限制: {Number(payload.max_count)} 条</Tag>
          )}
        </div>
      );

    case "CLEAN_MESSAGES":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {payload.raw_count !== undefined && (
            <Tag color="default">原始消息: {Number(payload.raw_count)} 条</Tag>
          )}
          {payload.cleaned_count !== undefined && (
            <Tag color="green">清洗留存: {Number(payload.cleaned_count)} 条</Tag>
          )}
          {payload.dropped_count !== undefined && (
            <Tag color="orange">过滤噪音: {Number(payload.dropped_count)} 条</Tag>
          )}
          {payload.retention_rate !== undefined && (
            <Tag color="geekblue">有效留存率: {Number(payload.retention_rate)}%</Tag>
          )}
        </div>
      );

    case "STATS_ANALYSIS":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {payload.message_count !== undefined && (
            <Tag color="blue">总消息数: {Number(payload.message_count)} 条</Tag>
          )}
          {payload.character_count !== undefined && (
            <Tag color="cyan">总字符数: {Number(payload.character_count)} 字</Tag>
          )}
          {payload.participant_count !== undefined && (
            <Tag color="purple">发言人数: {Number(payload.participant_count)} 人</Tag>
          )}
          {Boolean(payload.most_active_period) && (
            <Tag color="magenta">最高峰时段: {String(payload.most_active_period)}</Tag>
          )}
          {payload.emoji_count !== undefined && (
            <Tag color="gold">表情总数: {Number(payload.emoji_count)} 个</Tag>
          )}
        </div>
      );

    case "CHECKPOINT_RESTORE":
      return (
        <div style={{ marginBottom: 6 }}>
          <Tag color="cyan">已从 Checkpoint 恢复前置清洗与基础统计快照，跳过重复拉取</Tag>
        </div>
      );

    case "SAVE_SUMMARY":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Boolean(payload.date) && (
            <Tag color="green">归档日期: {String(payload.date)}</Tag>
          )}
          {payload.topics_persisted !== undefined && (
            <Tag color="blue">话题持久化: {Number(payload.topics_persisted)} 个</Tag>
          )}
          {payload.titles_persisted !== undefined && (
            <Tag color="purple">称号持久化: {Number(payload.titles_persisted)} 个</Tag>
          )}
          {Boolean(payload.checkpoint_saved) && (
            <Tag color="cyan">快照持久化: 成功 (可免 Token 重绘)</Tag>
          )}
        </div>
      );

    case "RENDER_REPORT":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Boolean(payload.format) && (
            <Tag color="blue">格式: {String(payload.format)}</Tag>
          )}
          {Boolean(payload.template) && (
            <Tag color="magenta">主题模板: {String(payload.template)}</Tag>
          )}
        </div>
      );

    case "DISPATCH_REPORT":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Boolean(payload.platform) && (
            <Tag color="cyan">目标平台: {String(payload.platform)}</Tag>
          )}
          {(Boolean(payload.format) || Boolean(payload.formats)) && (
            <Tag color="blue">
              分发格式:{" "}
              {Array.isArray(payload.formats)
                ? (payload.formats as string[]).join(", ")
                : String(payload.format || payload.formats)}
            </Tag>
          )}
          {payload.success !== undefined && (
            <Tag color={payload.success ? "success" : "error"}>
              {payload.success ? "分发完成" : "分发失败/回退"}
            </Tag>
          )}
          {payload.image_sent !== undefined && (
            <Tag color={payload.image_sent ? "green" : "volcano"}>
              图片消息: {payload.image_sent ? "已发送" : "未发送"}
            </Tag>
          )}
          {payload.html_sent !== undefined && (
            <Tag color={payload.html_sent ? "green" : "volcano"}>
              HTML消息: {payload.html_sent ? "已发送" : "未发送"}
            </Tag>
          )}
          {Boolean(payload.report_file) && (
            <Tag color="purple">产物文件: {String(payload.report_file)}</Tag>
          )}
        </div>
      );

    case "COMIC_STORYBOARD":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Boolean(payload.character_name) && (
            <Tag color="magenta">角色方案: {String(payload.character_name)}</Tag>
          )}
          {payload.storyboards_count !== undefined && (
            <Tag color="purple">分镜数: {Number(payload.storyboards_count)}</Tag>
          )}
          {payload.total_tokens !== undefined && Number(payload.total_tokens) > 0 && (
            <Tag color="volcano">Token: {Number(payload.total_tokens)}</Tag>
          )}
        </div>
      );

    case "COMIC_DRAWING":
      return (
        <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Boolean(payload.backend) && (
            <Tag color="magenta">绘图后端: {String(payload.backend)}</Tag>
          )}
          {payload.reference_images_count !== undefined && (
            <Tag color="cyan">参考图: {Number(payload.reference_images_count)} 张</Tag>
          )}
          {payload.success !== undefined && (
            <Tag color={payload.success ? "success" : "error"}>
              {payload.success ? "出图成功" : "出图失败"}
            </Tag>
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
          <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
            <Tag color={feats.topics !== false ? "blue" : "default"}>
              话题分析: {feats.topics !== false ? "已开启" : "未启用"}
            </Tag>
            <Tag color={feats.user_titles !== false ? "cyan" : "default"}>
              群友画像: {feats.user_titles !== false ? "已开启" : "未启用"}
            </Tag>
            <Tag color={feats.golden_quotes !== false ? "purple" : "default"}>
              精彩金句: {feats.golden_quotes !== false ? "已开启" : "未启用"}
            </Tag>
            <Tag color={feats.chat_quality !== false ? "geekblue" : "default"}>
              质量锐评: {feats.chat_quality !== false ? "已开启" : "未启用"}
            </Tag>
          </div>
        );
      }
      return null;

    default:
      return null;
  }
};
