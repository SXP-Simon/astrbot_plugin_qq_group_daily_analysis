import React from "react";
import { Descriptions, Tag, Typography, Tooltip, Space, Button } from "antd";
import {
  DatabaseOutlined,
  FileImageOutlined,
  PictureOutlined,
  FileTextOutlined,
  EyeOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { TraceRecord } from "../../../entities/trace/model/types";
import { TriggerTypeTag } from "../../../shared/ui/TriggerTypeTag";
import {
  formatDuration,
  formatTokens,
  formatTimestamp,
  formatPercent,
} from "../../../shared/lib/formatters";
import { useTheme } from "../../../shared/lib/useTheme";

const { Text } = Typography;

interface TraceSummaryCardProps {
  trace: TraceRecord;
  onPreviewFile: (filename: string, isHtml: boolean) => void;
  onDownloadFile: (filename: string, isHtml: boolean) => void;
}

export const TraceSummaryCard: React.FC<TraceSummaryCardProps> = ({
  trace,
  onPreviewFile,
  onDownloadFile,
}) => {
  const { isDark } = useTheme();

  const rawFiles =
    trace.report_files ||
    (Array.isArray(trace.extra?.report_files)
      ? (trace.extra.report_files as TraceRecord["report_files"])
      : []) ||
    [];
  const seenNames = new Set<string>();
  const reportFiles = rawFiles.filter((f) => {
    if (!f || !f.filename || seenNames.has(f.filename)) return false;
    seenNames.add(f.filename);
    return true;
  });

  return (
    <>
      {/* 基本信息 */}
      <Descriptions
        size="small"
        bordered
        column={2}
        labelStyle={{ width: 85, fontSize: 12 }}
        contentStyle={{ fontSize: 12 }}
      >
        <Descriptions.Item label="任务编号" span={2}>
          <Text
            copyable
            style={{
              fontFamily:
                "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
              fontSize: 12,
            }}
          >
            {trace.trace_id}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="分析群聊" span={2}>
          <span>
            {trace.group_name || "未知群"}{" "}
            <Text type="secondary">({trace.group_id})</Text>
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="接入平台">
          <Tag style={{ margin: 0 }}>
            {!trace.platform ||
            trace.platform === "auto" ||
            trace.platform === "default"
              ? "-"
              : trace.platform}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="触发方式">
          <TriggerTypeTag triggerType={trace.trigger_type} />
        </Descriptions.Item>
        <Descriptions.Item label="开始时间">
          <span>{formatTimestamp(trace.started_at)}</span>
        </Descriptions.Item>
        <Descriptions.Item label="执行总耗时">
          <span style={{ color: "#1677ff", fontWeight: 600 }}>
            {formatDuration(trace.duration_ms)}
          </span>
        </Descriptions.Item>
      </Descriptions>

      {/* 上下文演进与 Token */}
      {(trace.context_metrics || trace.token_usage) && (
        <Descriptions
          title={
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              <DatabaseOutlined style={{ marginRight: 6, color: "#1677ff" }} />
              消息处理与模型消耗
            </span>
          }
          size="small"
          bordered
          column={2}
          labelStyle={{ width: 100, fontSize: 12 }}
          contentStyle={{ fontSize: 12 }}
        >
          {trace.context_metrics && (
            <>
              <Descriptions.Item label="读取原始消息">
                <span>
                  {trace.context_metrics.raw_message_count.toLocaleString()} 条
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="有效消息留存">
                <span style={{ color: "#52c41a", fontWeight: 500 }}>
                  {trace.context_metrics.cleaned_message_count.toLocaleString()}{" "}
                  条 ({formatPercent(trace.context_metrics.compression_ratio)})
                </span>
              </Descriptions.Item>
            </>
          )}
          {trace.token_usage && (
            <>
              <Descriptions.Item label="模型消耗总量">
                <span style={{ fontWeight: 600 }}>
                  {formatTokens(trace.token_usage.total_tokens)}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="输入 / 输出">
                <span style={{ fontSize: 11 }}>
                  输入: {formatTokens(trace.token_usage.prompt_tokens)} / 输出:{" "}
                  {formatTokens(trace.token_usage.completion_tokens)}
                </span>
              </Descriptions.Item>
            </>
          )}
        </Descriptions>
      )}

      {/* 产物报告文件 */}
      {reportFiles.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <FileImageOutlined style={{ marginRight: 6, color: "#52c41a" }} />
            产物报告文件 ({reportFiles.length} 个)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {reportFiles.map((file, idx) => {
              const isHtml = Boolean(
                file.format === "html" ||
                  file.filename.toLowerCase().endsWith(".html") ||
                  file.filename.toLowerCase().endsWith(".htm")
              );
              const isComic = Boolean(
                file.report_type === "comic" ||
                  file.filename.toLowerCase().startsWith("comic_") ||
                  file.filename.startsWith("漫画_")
              );
              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px 12px",
                    background: isDark ? "rgba(255,255,255,0.03)" : "#f8fafc",
                    border: `1px solid ${
                      isDark ? "rgba(255,255,255,0.08)" : "#e2e8f0"
                    }`,
                    borderRadius: 4,
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      minWidth: 0,
                      flex: 1,
                      gap: 6,
                      overflow: "hidden",
                    }}
                  >
                    {isComic ? (
                      <PictureOutlined
                        style={{ color: "#eb2f96", flexShrink: 0 }}
                      />
                    ) : isHtml ? (
                      <FileTextOutlined
                        style={{ color: "#fa8c16", flexShrink: 0 }}
                      />
                    ) : (
                      <FileImageOutlined
                        style={{ color: "#1677ff", flexShrink: 0 }}
                      />
                    )}
                    <Tooltip title={file.filename} placement="topLeft">
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          minWidth: 0,
                        }}
                      >
                        {file.filename}
                      </span>
                    </Tooltip>
                    <Tag
                      color={isComic ? "magenta" : isHtml ? "orange" : "blue"}
                      style={{
                        margin: 0,
                        fontSize: 10,
                        lineHeight: "16px",
                        flexShrink: 0,
                      }}
                    >
                      {isComic ? "群漫画" : isHtml ? "HTML" : "日报长图"}
                    </Tag>
                    {file.size_bytes ? (
                      <Text
                        type="secondary"
                        style={{
                          fontSize: 11,
                          whiteSpace: "nowrap",
                          flexShrink: 0,
                        }}
                      >
                        ({(file.size_bytes / 1024).toFixed(1)} KB)
                      </Text>
                    ) : null}
                  </div>
                  <Space
                    size="small"
                    style={{ flexShrink: 0, whiteSpace: "nowrap" }}
                  >
                    <Button
                      size="small"
                      type="primary"
                      ghost
                      icon={<EyeOutlined />}
                      onClick={() => onPreviewFile(file.filename, isHtml)}
                      style={{ fontSize: 11, height: 24 }}
                    >
                      {isComic
                        ? "预览漫画"
                        : isHtml
                        ? "预览 HTML"
                        : "预览大图"}
                    </Button>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => onDownloadFile(file.filename, isHtml)}
                      style={{ fontSize: 11, height: 24 }}
                    >
                      下载
                    </Button>
                  </Space>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
};
