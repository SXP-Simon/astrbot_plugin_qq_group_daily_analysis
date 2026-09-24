import React from "react";
import {
  Modal,
  Button,
  Space,
  Descriptions,
  Card,
  Tag,
  Typography,
  theme,
} from "antd";
import {
  ThunderboltOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import {
  IncrementalBatchItem,
  IncrementalBatchTopic,
  IncrementalBatchGoldenQuote,
  ChatQualityDimension,
  ChatQualityReviewObject,
} from "../../../../entities/plugin-data/model/types";
import { formatTimestamp, formatTokens } from "../../../../shared/lib/formatters";
import { SANS_NUM_STYLE, handleCopyJson } from "../constants";

const { Text, Paragraph } = Typography;

interface BatchDetailModalProps {
  open: boolean;
  onClose: () => void;
  batchDetail: IncrementalBatchItem | null;
  loading: boolean;
}

export const BatchDetailModal: React.FC<BatchDetailModalProps> = ({
  open,
  onClose,
  batchDetail,
  loading,
}) => {
  const { token } = theme.useToken();

  return (
    <Modal
      title={
        <Space>
          <ThunderboltOutlined style={{ color: "#1677ff" }} />
          <span>
            增量批次详情:{" "}
            {batchDetail?.batch_id
              ? batchDetail.batch_id.length > 18
                ? `${batchDetail.batch_id.slice(0, 18)}...`
                : batchDetail.batch_id
              : ""}
          </span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button
          key="copy"
          icon={<CopyOutlined />}
          onClick={() => handleCopyJson(batchDetail)}
        >
          复制完整 JSON
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          关闭
        </Button>,
      ]}
      width={850}
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "30px 0" }}>
          <Text type="secondary">加载批次明细数据中...</Text>
        </div>
      ) : batchDetail ? (
        <Space direction="vertical" size="small" style={{ width: "100%" }}>
          <Descriptions
            size="small"
            bordered
            column={{ xs: 1, sm: 2, md: 2 }}
            style={{ marginBottom: 4 }}
            items={[
              {
                key: "group",
                label: "目标群聊",
                children: (
                  <Text strong style={SANS_NUM_STYLE}>
                    {batchDetail.group_id}
                  </Text>
                ),
              },
              {
                key: "time",
                label: "批次生成时间",
                children: (
                  <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
                    {formatTimestamp(batchDetail.timestamp)}
                  </span>
                ),
              },
              {
                key: "count",
                label: "消息与字符量",
                children: (
                  <span style={SANS_NUM_STYLE}>
                    {batchDetail.messages_count} 条 (
                    {(batchDetail.characters_count || 0).toLocaleString()} 字)
                  </span>
                ),
              },
              {
                key: "last_msg_time",
                label: "涵盖最新消息时间",
                children: batchDetail.last_message_timestamp ? (
                  <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
                    {formatTimestamp(batchDetail.last_message_timestamp)}
                  </span>
                ) : (
                  "-"
                ),
              },
              {
                key: "batch_id",
                label: "批次完整 ID",
                span: 2,
                children: (
                  <Space size={8}>
                    <Text copyable code style={{ fontSize: 12, ...SANS_NUM_STYLE }}>
                      {batchDetail.batch_id}
                    </Text>
                  </Space>
                ),
              },
              {
                key: "tokens",
                label: "Token 消耗",
                span: 2,
                children: batchDetail.token_usage ? (
                  <Space size={12}>
                    <span>
                      总计:{" "}
                      <Text strong style={SANS_NUM_STYLE}>
                        {formatTokens(batchDetail.token_usage.total_tokens || 0)}
                      </Text>
                    </span>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      (Prompt:{" "}
                      {formatTokens(batchDetail.token_usage.prompt_tokens || 0)} /
                      Completion:{" "}
                      {formatTokens(
                        batchDetail.token_usage.completion_tokens || 0
                      )}
                      )
                    </Text>
                  </Space>
                ) : (
                  "-"
                ),
              },
            ]}
          />

          {batchDetail.chat_quality_review ? (
            <Card size="small" title="聊天质量与氛围评价">
              {typeof batchDetail.chat_quality_review === "string" ? (
                <Paragraph style={{ margin: 0, fontSize: 12 }}>
                  {batchDetail.chat_quality_review}
                </Paragraph>
              ) : typeof batchDetail.chat_quality_review === "object" ? (
                (() => {
                  const review =
                    batchDetail.chat_quality_review as ChatQualityReviewObject;
                  return (
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      {review.title && (
                        <Text
                          strong
                          style={{
                            fontSize: 13,
                            color: token.colorTextHeading,
                          }}
                        >
                          {review.title}
                          {review.subtitle ? ` · ${review.subtitle}` : ""}
                        </Text>
                      )}
                      {Array.isArray(review.dimensions) ? (
                        review.dimensions.map(
                          (dim: ChatQualityDimension, idx: number) => (
                            <div key={idx} style={{ fontSize: 12, marginTop: 4 }}>
                              <Tag color="purple">
                                {dim.name || `维度 ${idx + 1}`} (
                                {dim.percentage || 0}%)
                              </Tag>
                              <Text type="secondary">{dim.comment}</Text>
                            </div>
                          )
                        )
                      ) : (
                        <Paragraph style={{ margin: 0, fontSize: 12 }}>
                          {JSON.stringify(batchDetail.chat_quality_review)}
                        </Paragraph>
                      )}
                    </Space>
                  );
                })()
              ) : null}
            </Card>
          ) : null}

          {Array.isArray(batchDetail.topics) && batchDetail.topics.length > 0 && (
            <Card
              size="small"
              title={`提炼话题 (${batchDetail.topics.length} 个)`}
            >
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {batchDetail.topics.map(
                  (t: IncrementalBatchTopic, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        fontSize: 12,
                        paddingBottom: 6,
                        borderBottom:
                          idx < batchDetail.topics!.length - 1
                            ? `1px dashed ${token.colorBorderSecondary}`
                            : "none",
                      }}
                    >
                      <Space size={6}>
                        <Tag
                          color={
                            (t.heat_score || 0) >= 80
                              ? "volcano"
                              : (t.heat_score || 0) >= 50
                              ? "orange"
                              : "geekblue"
                          }
                        >
                          {t.title || "未命名话题"} ({t.heat_score || 0}℃)
                        </Tag>
                        {t.category ? <Tag>{String(t.category)}</Tag> : null}
                      </Space>
                      {t.description || t.summary ? (
                        <div
                          style={{
                            marginTop: 4,
                            color: token.colorTextSecondary,
                          }}
                        >
                          {String(t.description || t.summary)}
                        </div>
                      ) : null}
                    </div>
                  )
                )}
              </Space>
            </Card>
          )}

          {Array.isArray(batchDetail.golden_quotes) &&
            batchDetail.golden_quotes.length > 0 && (
              <Card
                size="small"
                title={`精彩金句 (${batchDetail.golden_quotes.length} 条)`}
              >
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {batchDetail.golden_quotes.map(
                    (q: IncrementalBatchGoldenQuote, idx: number) => (
                      <div key={idx} style={{ fontSize: 12 }}>
                        <Text strong style={{ color: "#d48806" }}>
                          “{String(q.content || q.text || JSON.stringify(q))}”
                        </Text>
                        {(q.sender_nickname || q.sender_name || q.author) && (
                          <Text type="secondary" style={{ marginLeft: 8 }}>
                            ——{" "}
                            {String(
                              q.sender_nickname || q.sender_name || q.author
                            )}
                          </Text>
                        )}
                      </div>
                    )
                  )}
                </Space>
              </Card>
            )}

          <div>
            <Text
              strong
              style={{ fontSize: 12, marginBottom: 4, display: "block" }}
            >
              底层完整批次数据 (JSON):
            </Text>
            <pre
              style={{
                fontSize: 11,
                fontFamily:
                  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
                background: token.colorFillAlter,
                color: token.colorText,
                border: `1px solid ${token.colorBorderSecondary}`,
                padding: "8px 10px",
                borderRadius: 4,
                maxHeight: 280,
                overflowY: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                margin: 0,
              }}
            >
              {JSON.stringify(batchDetail, null, 2)}
            </pre>
          </div>
        </Space>
      ) : null}
    </Modal>
  );
};
