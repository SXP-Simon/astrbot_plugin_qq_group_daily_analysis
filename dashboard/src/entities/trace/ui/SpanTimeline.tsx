import React, { useState } from "react";
import {
  Timeline,
  Tag,
  Typography,
  Progress,
  Space,
  Tooltip,
  Collapse,
  Tabs,
  Button,
  message,
  theme,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  DownOutlined,
  RightOutlined,
  FileTextOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import { TraceSpan } from "../model/types";
import { formatDuration, formatStageName } from "../../../shared/lib/formatters";
import { copyToClipboard } from "../../../shared/lib/clipboard";

const { Text } = Typography;

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
}

/**
 * 依据各阶段特性（本地计算 vs 外部协议 vs 大模型 vs 绘图）制定 SLA 健康基线与超时预算
 */
function getStageSlaThreshold(stageName: string): { thresholdMs: number; description: string } {
  const norm = (stageName || "").toUpperCase();
  if (
    norm.includes("LLM") ||
    norm.includes("话题") ||
    norm.includes("画像") ||
    norm.includes("金句")
  ) {
    return { thresholdMs: 120000, description: "大模型多轮分析健康阈值 120s" };
  }
  if (
    norm.includes("COMIC") ||
    norm.includes("漫画") ||
    norm.includes("DRAW") ||
    norm.includes("T2I")
  ) {
    return { thresholdMs: 180000, description: "文生图/绘图排队健康阈值 180s" };
  }
  if (
    norm.includes("RENDER") ||
    norm.includes("渲染") ||
    norm.includes("REPORT")
  ) {
    return { thresholdMs: 45000, description: "长图渲染与平台发送健康阈值 45s" };
  }
  if (norm.includes("FETCH") || norm.includes("拉取")) {
    return { thresholdMs: 20000, description: "平台消息抓取健康阈值 20s" };
  }
  if (
    norm.includes("CLEAN") ||
    norm.includes("清洗") ||
    norm.includes("STATS") ||
    norm.includes("统计") ||
    norm.includes("SAVE") ||
    norm.includes("持久化")
  ) {
    return { thresholdMs: 5000, description: "本地计算/SQLite 处理健康阈值 5s" };
  }
  return { thresholdMs: 30000, description: "常规流程健康阈值 30s" };
}

export const SpanTimeline: React.FC<SpanTimelineProps> = ({
  spans,
  totalDurationMs = 1,
}) => {
  const { token } = theme.useToken();
  const [expandedSpanIds, setExpandedSpanIds] = useState<string[]>([]);

  if (!spans || spans.length === 0) {
    return <Text type="secondary">无执行阶段记录</Text>;
  }

  const toggleExpand = (id: string) => {
    setExpandedSpanIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const items = spans.map((span, idx) => {
    const spanKey = span.span_id || `span_${idx}_${span.stage_name}`;
    const duration = span.duration_ms || 0;
    const durationPct = Math.min(
      100,
      Math.max(2, Math.round((duration / Math.max(1, totalDurationMs)) * 100))
    );

    const { thresholdMs, description: slaDesc } = getStageSlaThreshold(span.stage_name);
    const isSlaExceeded = duration > thresholdMs;
    const isFailed = span.status === "failed" || span.status === "error";
    const isRunning = span.status === "running";

    let color = "#52c41a";
    let icon = <CheckCircleOutlined style={{ color: "#52c41a" }} />;
    let tagColor = "success";

    if (isFailed) {
      color = "#ff4d4f";
      icon = <CloseCircleOutlined style={{ color: "#ff4d4f" }} />;
      tagColor = "error";
    } else if (isRunning) {
      color = "#1677ff";
      icon = <SyncOutlined spin style={{ color: "#1677ff" }} />;
      tagColor = "processing";
    } else if (isSlaExceeded) {
      color = "#fa8c16";
      icon = <CheckCircleOutlined style={{ color: "#fa8c16" }} />;
      tagColor = "warning";
    }

    const isExpanded = expandedSpanIds.includes(spanKey);
    const hasPayload = span.payload && Object.keys(span.payload).length > 0;

    return {
      dot: icon,
      children: (
        <div
          style={{
            marginBottom: 12,
            background: isExpanded ? token.colorFillAlter : "transparent",
            borderRadius: 6,
            padding: isExpanded ? "8px 10px" : "0",
            transition: "all 0.2s ease",
          }}
        >
          {/* 阶段标题与耗时条 */}
          <div
            onClick={() => toggleExpand(spanKey)}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <Space size={6}>
              {isExpanded ? (
                <DownOutlined style={{ fontSize: 10, color: token.colorTextTertiary }} />
              ) : (
                <RightOutlined style={{ fontSize: 10, color: token.colorTextTertiary }} />
              )}
              <span style={{ fontWeight: 600, fontSize: 13, color: token.colorText }}>
                {formatStageName(span.stage_name)}
              </span>
              {isSlaExceeded && (
                <Tooltip title={`该阶段耗时已超出预期的健康基线 (${slaDesc})`}>
                  <Tag
                    color="warning"
                    icon={<WarningOutlined />}
                    style={{ margin: 0, fontSize: 10, padding: "0 4px", lineHeight: "18px" }}
                  >
                    耗时超出健康基线
                  </Tag>
                </Tooltip>
              )}
            </Space>

            <Space size={6}>
              <span style={{ fontSize: 11, color: token.colorTextSecondary }}>
                占 {durationPct}%
              </span>
              <Tag
                color={tagColor}
                style={{
                  fontSize: 11,
                  borderRadius: 4,
                  margin: 0,
                  fontWeight: 600,
                }}
              >
                {formatDuration(span.duration_ms)}
              </Tag>
            </Space>
          </div>

          <Progress
            percent={durationPct}
            size="small"
            showInfo={false}
            strokeColor={color}
            style={{ margin: "4px 0 2px 0" }}
          />

          {/* 展开的阶段参数与日志详情 */}
          {isExpanded && (
            <div style={{ marginTop: 8 }}>
              {isFailed && (
                <div
                  style={{
                    padding: "6px 8px",
                    background: token.colorErrorBg,
                    border: `1px solid ${token.colorErrorBorder}`,
                    borderRadius: 4,
                    color: token.colorErrorText,
                    fontSize: 12,
                    marginBottom: 6,
                  }}
                >
                  <Text type="danger" strong>
                    阶段异常：
                  </Text>
                  <span>{String(span.payload?.error || "该流程执行异常中断")}</span>
                </div>
              )}

              {Array.isArray(span.payload?.subtask_errors) &&
                span.payload.subtask_errors.length > 0 && (
                  <div
                    style={{
                      padding: "6px 8px",
                      background: token.colorWarningBg,
                      border: `1px solid ${token.colorWarningBorder}`,
                      borderRadius: 4,
                      color: token.colorWarningText,
                      fontSize: 12,
                      marginBottom: 6,
                    }}
                  >
                    <Text style={{ color: "#d46b08" }} strong>
                      部分子任务调用异常：
                    </Text>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {span.payload.subtask_errors.map((err: string, i: number) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* 1. 消息拉取阶段摘要 */}
              {span.stage_name === "FETCH_MESSAGES" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {span.payload.fetched_count !== undefined && (
                    <Tag color="blue">拉取消息: {Number(span.payload.fetched_count)} 条</Tag>
                  )}
                  {span.payload.days !== undefined && (
                    <Tag color="cyan">时间跨度: {Number(span.payload.days)} 天</Tag>
                  )}
                  {span.payload.max_count !== undefined && (
                    <Tag color="default">最大限制: {Number(span.payload.max_count)} 条</Tag>
                  )}
                </div>
              ) : null}

              {/* 2. 消息清洗阶段摘要 */}
              {span.stage_name === "CLEAN_MESSAGES" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {span.payload.raw_count !== undefined && (
                    <Tag color="default">原始消息: {Number(span.payload.raw_count)} 条</Tag>
                  )}
                  {span.payload.cleaned_count !== undefined && (
                    <Tag color="green">清洗留存: {Number(span.payload.cleaned_count)} 条</Tag>
                  )}
                  {span.payload.dropped_count !== undefined && (
                    <Tag color="orange">过滤噪音: {Number(span.payload.dropped_count)} 条</Tag>
                  )}
                  {span.payload.retention_rate !== undefined && (
                    <Tag color="geekblue">有效留存率: {Number(span.payload.retention_rate)}%</Tag>
                  )}
                </div>
              ) : null}

              {/* 3. 基础统计阶段摘要 */}
              {span.stage_name === "STATS_ANALYSIS" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {span.payload.message_count !== undefined && (
                    <Tag color="blue">总消息数: {Number(span.payload.message_count)} 条</Tag>
                  )}
                  {span.payload.character_count !== undefined && (
                    <Tag color="cyan">总字符数: {Number(span.payload.character_count)} 字</Tag>
                  )}
                  {span.payload.participant_count !== undefined && (
                    <Tag color="purple">发言人数: {Number(span.payload.participant_count)} 人</Tag>
                  )}
                  {Boolean(span.payload.most_active_period) && (
                    <Tag color="magenta">最高峰时段: {String(span.payload.most_active_period)}</Tag>
                  )}
                  {span.payload.emoji_count !== undefined && (
                    <Tag color="gold">表情总数: {Number(span.payload.emoji_count)} 个</Tag>
                  )}
                </div>
              ) : null}

              {/* 4. 断点恢复阶段 */}
              {span.stage_name === "CHECKPOINT_RESTORE" && (
                <div style={{ marginBottom: 6 }}>
                  <Tag color="cyan">已从 Checkpoint 恢复前置清洗与基础统计快照，跳过重复拉取</Tag>
                </div>
              )}

              {/* 5. 摘要持久化与快照 */}
              {span.stage_name === "SAVE_SUMMARY" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Boolean(span.payload.date) && (
                    <Tag color="green">归档日期: {String(span.payload.date)}</Tag>
                  )}
                  {span.payload.topics_persisted !== undefined && (
                    <Tag color="blue">话题持久化: {Number(span.payload.topics_persisted)} 个</Tag>
                  )}
                  {span.payload.titles_persisted !== undefined && (
                    <Tag color="purple">称号持久化: {Number(span.payload.titles_persisted)} 个</Tag>
                  )}
                  {Boolean(span.payload.checkpoint_saved) && (
                    <Tag color="cyan">快照持久化: 成功 (可免 Token 重绘)</Tag>
                  )}
                </div>
              ) : null}

              {/* 6. 报告渲染与分发 */}
              {span.stage_name === "RENDER_REPORT" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Boolean(span.payload.format) && (
                    <Tag color="blue">格式: {String(span.payload.format)}</Tag>
                  )}
                  {Boolean(span.payload.template) && (
                    <Tag color="magenta">主题模板: {String(span.payload.template)}</Tag>
                  )}
                </div>
              ) : null}

              {span.stage_name === "DISPATCH_REPORT" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Boolean(span.payload.format) && (
                    <Tag color="blue">分发格式: {String(span.payload.format)}</Tag>
                  )}
                  {Boolean(span.payload.platform) && (
                    <Tag color="cyan">目标平台: {String(span.payload.platform)}</Tag>
                  )}
                </div>
              ) : null}

              {/* 功能开关与子模块启用状态展示 */}
              {span.stage_name === "LLM_ANALYSIS" &&
              span.payload?.enabled_features &&
              typeof span.payload.enabled_features === "object" ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  <Tag
                    color={
                      (span.payload.enabled_features as Record<string, boolean>).topics !== false
                        ? "blue"
                        : "default"
                    }
                  >
                    话题分析:{" "}
                    {(span.payload.enabled_features as Record<string, boolean>).topics !== false
                      ? "已开启"
                      : "未启用"}
                  </Tag>
                  <Tag
                    color={
                      (span.payload.enabled_features as Record<string, boolean>).user_titles !== false
                        ? "cyan"
                        : "default"
                    }
                  >
                    群友画像:{" "}
                    {(span.payload.enabled_features as Record<string, boolean>).user_titles !== false
                      ? "已开启"
                      : "未启用"}
                  </Tag>
                  <Tag
                    color={
                      (span.payload.enabled_features as Record<string, boolean>).golden_quotes !== false
                        ? "purple"
                        : "default"
                    }
                  >
                    精彩金句:{" "}
                    {(span.payload.enabled_features as Record<string, boolean>).golden_quotes !== false
                      ? "已开启"
                      : "未启用"}
                  </Tag>
                  <Tag
                    color={
                      (span.payload.enabled_features as Record<string, boolean>).chat_quality !== false
                        ? "geekblue"
                        : "default"
                    }
                  >
                    质量锐评:{" "}
                    {(span.payload.enabled_features as Record<string, boolean>).chat_quality !== false
                      ? "已开启"
                      : "未启用"}
                  </Tag>
                </div>
              ) : null}

              {/* LLM 真实提示词 Prompt 查看与复制 */}
              {span.stage_name === "LLM_ANALYSIS" &&
              span.payload?.prompts &&
              typeof span.payload.prompts === "object" &&
              Object.keys(span.payload.prompts).length > 0 ? (
                <div style={{ marginBottom: 8, marginTop: 4 }}>
                  <Collapse
                    size="small"
                    ghost
                    items={[
                      {
                        key: "prompts",
                        label: (
                          <Space>
                            <FileTextOutlined style={{ color: "#1677ff" }} />
                            <span style={{ fontWeight: 600, fontSize: 12 }}>
                              查看本次任务 LLM 实际提示词 (Prompts)
                            </span>
                            <Tag color="blue" style={{ fontSize: 10 }}>
                              {Object.keys(span.payload.prompts).length} 个子任务
                            </Tag>
                          </Space>
                        ),
                        children: (
                          <Tabs
                            size="small"
                            items={Object.entries(
                              span.payload.prompts as Record<
                                string,
                                {
                                  prompt?: string;
                                  system_prompt?: string;
                                  provider_id?: string;
                                } | string
                              >
                            ).map(([analyzerName, pInfo]) => {
                              const isStr = typeof pInfo === "string";
                              const promptContent = isStr
                                ? pInfo
                                : pInfo?.prompt || JSON.stringify(pInfo);
                              const providerId = !isStr
                                ? pInfo?.provider_id
                                : undefined;
                              return {
                                key: analyzerName,
                                label: analyzerName,
                                children: (
                                  <div>
                                    <div
                                      style={{
                                        display: "flex",
                                        justifyContent: "space-between",
                                        alignItems: "center",
                                        marginBottom: 4,
                                      }}
                                    >
                                      <Text
                                        type="secondary"
                                        style={{ fontSize: 11 }}
                                      >
                                        Provider: {providerId || "默认"} | 长度:{" "}
                                        {promptContent.length} 字符
                                      </Text>
                                      <Button
                                        size="small"
                                        type="text"
                                        icon={<CopyOutlined />}
                                        onClick={() => {
                                          copyToClipboard(promptContent);
                                          message.success(`已复制 ${analyzerName} 提示词`);
                                        }}
                                      >
                                        复制 Prompt
                                      </Button>
                                    </div>
                                    <pre
                                      style={{
                                        fontSize: 11,
                                        fontFamily:
                                          'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                                        background: token.colorFillAlter,
                                        color: token.colorText,
                                        border: `1px solid ${token.colorBorderSecondary}`,
                                        padding: "6px 8px",
                                        borderRadius: 4,
                                        margin: 0,
                                        maxHeight: 180,
                                        overflowY: "auto",
                                        whiteSpace: "pre-wrap",
                                        wordBreak: "break-all",
                                      }}
                                    >
                                      {promptContent}
                                    </pre>
                                  </div>
                                ),
                              };
                            })}
                          />
                        ),
                      },
                    ]}
                  />
                </div>
              ) : null}

              {/* 漫画分镜与绘图阶段摘要 */}
              {span.stage_name === "COMIC_STORYBOARD" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Boolean(span.payload.character_name) && (
                    <Tag color="magenta">角色方案: {String(span.payload.character_name)}</Tag>
                  )}
                  {span.payload.storyboards_count !== undefined && (
                    <Tag color="purple">分镜数: {Number(span.payload.storyboards_count)}</Tag>
                  )}
                  {span.payload.total_tokens !== undefined && Number(span.payload.total_tokens) > 0 && (
                    <Tag color="volcano">Token: {Number(span.payload.total_tokens)}</Tag>
                  )}
                </div>
              ) : null}

              {span.stage_name === "COMIC_DRAWING" && span.payload ? (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Boolean(span.payload.backend) && (
                    <Tag color="magenta">绘图后端: {String(span.payload.backend)}</Tag>
                  )}
                  {span.payload.reference_images_count !== undefined && (
                    <Tag color="cyan">参考图: {Number(span.payload.reference_images_count)} 张</Tag>
                  )}
                  {span.payload.success !== undefined && (
                    <Tag color={span.payload.success ? "success" : "error"}>
                      {span.payload.success ? "出图成功" : "出图失败"}
                    </Tag>
                  )}
                </div>
              ) : null}

              {span.stage_name === "LLM_ANALYSIS" &&
                span.payload?.topics_count === 0 &&
                (!span.payload?.prompt_tokens || span.payload?.prompt_tokens === 0) &&
                (!Array.isArray(span.payload?.subtask_errors) ||
                  span.payload?.subtask_errors.length === 0) && (
                  <div
                    style={{
                      padding: "6px 8px",
                      background: token.colorWarningBg,
                      border: `1px solid ${token.colorWarningBorder}`,
                      borderRadius: 4,
                      color: token.colorWarningText,
                      fontSize: 12,
                      marginBottom: 6,
                    }}
                  >
                    <Text style={{ color: "#d46b08" }} strong>
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "ℹ️ 本次任务已在配置中关闭所有大模型文本分析模块"
                        : "⚠️ 大模型分析未产出有效内容："}
                    </Text>
                    <div style={{ marginTop: 2 }}>
                      {span.payload?.enabled_features &&
                      Object.values(span.payload.enabled_features).every((v) => !v)
                        ? "配置项中话题、群友画像、金句和质量锐评均未开启。"
                        : "模型未消耗 Token 或未能解析出任何话题/画像/金句，请检查大模型 Provider 连接与配置。"}
                    </div>
                  </div>
                )}

              {hasPayload ? (
                <div>
                  <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 4 }}>
                    阶段调用参数与执行产物明细：
                  </div>
                  <pre
                    style={{
                      fontSize: 11,
                      fontFamily:
                        'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                      background: token.colorFillAlter,
                      color: token.colorText,
                      border: `1px solid ${token.colorBorderSecondary}`,
                      padding: "6px 8px",
                      borderRadius: 4,
                      margin: 0,
                      maxHeight: 140,
                      overflowY: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                    }}
                  >
                    {JSON.stringify(span.payload, null, 2)}
                  </pre>
                </div>
              ) : (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  阶段执行正常，无额外上下文字段
                </Text>
              )}
            </div>
          )}
        </div>
      ),
    };
  });

  return <Timeline items={items} style={{ marginTop: 12 }} />;
};

