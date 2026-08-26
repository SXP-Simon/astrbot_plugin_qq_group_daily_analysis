import React, { useState } from "react";
import { Collapse, Tabs, Tag, Space, Typography, Button, message, theme } from "antd";
import {
  FileTextOutlined,
  CopyOutlined,
  UserOutlined,
  CodeOutlined,
  CheckCircleOutlined,
  AppstoreOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { formatTokens } from "../../../shared/lib/formatters";

const { Text } = Typography;

export interface PromptDetail {
  prompt?: string;
  system_prompt?: string;
  provider_id?: string;
  model?: string;
  provider_type?: string;
  tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  completion?: string;
}

interface PromptsInspectorProps {
  prompts?: Record<string, PromptDetail | string>;
}

const ANALYZER_NAME_MAP: Record<string, string> = {
  topics: "话题分析",
  user_titles: "群友画像",
  golden_quotes: "群聊金句",
  chat_quality: "质量锐评",
  group_sentiment: "情感分析",
  activity_prediction: "活跃预测",
  comic: "群漫画生成",
};

export const PromptsInspector: React.FC<PromptsInspectorProps> = ({ prompts }) => {
  const { token } = theme.useToken();
  const [activeTab, setActiveTab] = useState<string>("");

  if (!prompts || typeof prompts !== "object" || Object.keys(prompts).length === 0) {
    return null;
  }

  const promptEntries = Object.entries(prompts);
  const currentKey = activeTab || promptEntries[0]?.[0] || "";

  return (
    <div style={{ marginBottom: 8, marginTop: 4 }}>
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: "prompts",
            label: (
              <Space>
                <FileTextOutlined style={{ color: "#2563eb" }} />
                <span style={{ fontWeight: 600, fontSize: 12 }}>
                  各分析模块运行提示词与大模型产物 (Prompts & Output)
                </span>
                <Tag color="blue" style={{ fontSize: 10 }}>
                  {promptEntries.length} 个子模块
                </Tag>
              </Space>
            ),
            children: (
              <div>
                <Tabs
                  size="small"
                  activeKey={currentKey}
                  onChange={setActiveTab}
                  items={promptEntries.map(([analyzerName, pInfo]) => {
                    const isStr = typeof pInfo === "string";
                    const detail: PromptDetail = isStr
                      ? { prompt: pInfo }
                      : pInfo || {};

                    const promptText = detail.prompt || "";
                    const systemPrompt = detail.system_prompt || "";
                    const completionText = detail.completion || "";
                    const providerId = detail.provider_id;
                    const modelId = detail.model;
                    const tokens = detail.tokens || 0;
                    const displayName = ANALYZER_NAME_MAP[analyzerName] || analyzerName;
                    const showSubLabel = displayName !== analyzerName && !analyzerName.match(/[\u4e00-\u9fa5]/);

                    return {
                      key: analyzerName,
                      label: (
                        <span>
                          {displayName}
                          {showSubLabel && (
                            <span style={{ fontSize: 10, color: token.colorTextSecondary, marginLeft: 4 }}>
                              ({analyzerName})
                            </span>
                          )}
                        </span>
                      ),
                      children: (
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {/* 元数据状态栏 */}
                          <div
                            style={{
                              display: "flex",
                              flexWrap: "wrap",
                              justifyContent: "space-between",
                              alignItems: "center",
                              padding: "4px 8px",
                              background: token.colorFillAlter,
                              borderRadius: 4,
                              fontSize: 11,
                            }}
                          >
                            <Space size={8} wrap>
                              {providerId && (
                                <span style={{ fontFamily: "monospace" }}>
                                  <ApartmentOutlined style={{ marginRight: 3 }} />
                                  Provider: <b>{providerId}</b>
                                </span>
                              )}
                              {modelId && (
                                <span style={{ fontFamily: "monospace" }}>
                                  <AppstoreOutlined style={{ marginRight: 3 }} />
                                  Model: <b>{modelId}</b>
                                </span>
                              )}
                              {tokens > 0 && (
                                <Tag color="purple" style={{ margin: 0, fontSize: 10, fontFamily: "monospace" }}>
                                  {formatTokens(tokens)} Tokens
                                </Tag>
                              )}
                            </Space>

                            <Button
                              size="small"
                              type="text"
                              icon={<CopyOutlined />}
                              onClick={() => {
                                const fullDump = `=== System Prompt ===\n${systemPrompt}\n\n=== User Prompt ===\n${promptText}\n\n=== Completion ===\n${completionText}`;
                                copyToClipboard(fullDump);
                                message.success(`已复制 ${displayName} 完整上下文`);
                              }}
                            >
                              复制全部上下文
                            </Button>
                          </div>

                          {/* 1. 系统/人格设定提示词 (System Prompt) */}
                          {systemPrompt && (
                            <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 4, padding: "6px 8px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                                <Text strong style={{ fontSize: 11, color: token.colorText }}>
                                  <UserOutlined style={{ color: "#7c3aed", marginRight: 4 }} />
                                  系统人设提示词 (System Prompt)
                                </Text>
                                <Button
                                  size="small"
                                  type="link"
                                  style={{ fontSize: 11, padding: 0, height: "auto" }}
                                  onClick={() => {
                                    copyToClipboard(systemPrompt);
                                    message.success("已复制 System Prompt");
                                  }}
                                >
                                  复制
                                </Button>
                              </div>
                              <pre
                                style={{
                                  fontSize: 11,
                                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                                  background: token.colorFillAlter,
                                  color: token.colorText,
                                  padding: "6px 8px",
                                  borderRadius: 4,
                                  margin: 0,
                                  maxHeight: 120,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                }}
                              >
                                {systemPrompt}
                              </pre>
                            </div>
                          )}

                          {/* 2. 任务输入提示词 (User Prompt) */}
                          {promptText && (
                            <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 4, padding: "6px 8px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                                <Text strong style={{ fontSize: 11, color: token.colorText }}>
                                  <CodeOutlined style={{ color: "#2563eb", marginRight: 4 }} />
                                  任务分析输入 (User Prompt)
                                  <span style={{ fontSize: 10, color: token.colorTextSecondary, marginLeft: 6, fontWeight: "normal" }}>
                                    ({promptText.length} 字符)
                                  </span>
                                </Text>
                                <Button
                                  size="small"
                                  type="link"
                                  style={{ fontSize: 11, padding: 0, height: "auto" }}
                                  onClick={() => {
                                    copyToClipboard(promptText);
                                    message.success("已复制 User Prompt");
                                  }}
                                >
                                  复制
                                </Button>
                              </div>
                              <pre
                                style={{
                                  fontSize: 11,
                                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                                  background: token.colorFillAlter,
                                  color: token.colorText,
                                  padding: "6px 8px",
                                  borderRadius: 4,
                                  margin: 0,
                                  maxHeight: 160,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                }}
                              >
                                {promptText}
                              </pre>
                            </div>
                          )}

                          {/* 3. 模型产物响应文本 (Model Response) */}
                          {completionText && (
                            <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 4, padding: "6px 8px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                                <Text strong style={{ fontSize: 11, color: token.colorText }}>
                                  <CheckCircleOutlined style={{ color: "#16a34a", marginRight: 4 }} />
                                  大模型返回结果 (Completion Response)
                                </Text>
                                <Button
                                  size="small"
                                  type="link"
                                  style={{ fontSize: 11, padding: 0, height: "auto" }}
                                  onClick={() => {
                                    copyToClipboard(completionText);
                                    message.success("已复制大模型返回结果");
                                  }}
                                >
                                  复制
                                </Button>
                              </div>
                              <pre
                                style={{
                                  fontSize: 11,
                                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                                  background: token.colorFillAlter,
                                  color: token.colorText,
                                  padding: "6px 8px",
                                  borderRadius: 4,
                                  margin: 0,
                                  maxHeight: 140,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                }}
                              >
                                {completionText}
                              </pre>
                            </div>
                          )}
                        </div>
                      ),
                    };
                  })}
                />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};
