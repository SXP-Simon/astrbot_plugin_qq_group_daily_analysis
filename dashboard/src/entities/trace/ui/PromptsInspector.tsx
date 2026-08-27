import React, { useState } from "react";
import { Collapse, Tabs, Space, Button, message, theme } from "antd";
import {
  FileTextOutlined,
  CopyOutlined,
  UserOutlined,
  CodeOutlined,
  CheckCircleOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { formatTokens } from "../../../shared/lib/formatters";

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
  const isDark = token.colorBgBase === "#000000" || token.colorBgContainer?.startsWith("#1");

  if (!prompts || typeof prompts !== "object" || Object.keys(prompts).length === 0) {
    return null;
  }

  const promptEntries = Object.entries(prompts);
  const currentKey = activeTab || promptEntries[0]?.[0] || "";

  return (
    <div
      style={{
        marginTop: 10,
        marginBottom: 8,
        border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
        borderRadius: 6,
        overflow: "hidden",
        background: isDark ? "#161b22" : "#ffffff",
      }}
    >
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: "prompts",
            label: (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", paddingRight: 4 }}>
                <Space size={6}>
                  <FileTextOutlined style={{ color: "#2563eb" }} />
                  <span style={{ fontWeight: 600, fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                    各分析模块运行提示词与大模型产物 (Prompts & Output)
                  </span>
                </Space>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 3,
                    background: isDark ? "rgba(37, 99, 235, 0.12)" : "#eff6ff",
                    color: isDark ? "#60a5fa" : "#1d4ed8",
                    border: `1px solid ${isDark ? "rgba(37, 99, 235, 0.25)" : "#bfdbfe"}`,
                  }}
                >
                  {promptEntries.length} 个子模块
                </span>
              </div>
            ),
            children: (
              <div
                style={{
                  background: isDark ? "#0d1117" : "#f8fafc",
                  borderTop: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                  padding: "10px 12px",
                  borderRadius: "0 0 6px 6px",
                }}
              >
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

                    const showModel = Boolean(
                      modelId &&
                      modelId !== providerId &&
                      !providerId?.includes(modelId)
                    );
                    const providerDisplay = providerId
                      ? showModel
                        ? `${providerId} / ${modelId}`
                        : providerId
                      : modelId;

                    return {
                      key: analyzerName,
                      label: (
                        <span style={{ fontSize: 12 }}>
                          {displayName}
                          {showSubLabel && (
                            <span style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b", marginLeft: 4 }}>
                              ({analyzerName})
                            </span>
                          )}
                        </span>
                      ),
                      children: (
                        <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingTop: 4 }}>
                          {/* 元数据状态栏 */}
                          <div
                            style={{
                              display: "flex",
                              flexWrap: "wrap",
                              justifyContent: "space-between",
                              alignItems: "center",
                              padding: "6px 10px",
                              background: isDark ? "#161b22" : "#ffffff",
                              border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                              borderRadius: 4,
                              fontSize: 11,
                              gap: 8,
                            }}
                          >
                            <Space size={10} wrap>
                              {providerDisplay && (
                                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                                  <ApartmentOutlined style={{ color: "#2563eb", fontSize: 12 }} />
                                  <span style={{ color: isDark ? "#8b949e" : "#64748b" }}>Provider:</span>
                                  <span
                                    className="font-mono"
                                    style={{
                                      fontWeight: 600,
                                      color: isDark ? "#e2e8f0" : "#1e293b",
                                      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                                    }}
                                  >
                                    {providerDisplay}
                                  </span>
                                </span>
                              )}
                              {tokens > 0 && (
                                <span
                                  className="font-mono"
                                  style={{
                                    fontSize: 10,
                                    padding: "1px 6px",
                                    borderRadius: 3,
                                    background: isDark ? "rgba(147, 51, 234, 0.15)" : "#faf5ff",
                                    color: isDark ? "#c084fc" : "#7e22ce",
                                    border: `1px solid ${isDark ? "rgba(147, 51, 234, 0.3)" : "#e9d5ff"}`,
                                    fontWeight: 500,
                                  }}
                                >
                                  {formatTokens(tokens)} Tokens
                                </span>
                              )}
                            </Space>

                            <Button
                              size="small"
                              type="text"
                              icon={<CopyOutlined style={{ fontSize: 11 }} />}
                              style={{ fontSize: 11, height: 24, padding: "0 6px", color: isDark ? "#cbd5e1" : "#475569" }}
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
                            <div
                              style={{
                                border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                borderRadius: 4,
                                overflow: "hidden",
                                background: isDark ? "#161b22" : "#ffffff",
                                boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  padding: "5px 10px",
                                  background: isDark ? "#21262d" : "#f1f5f9",
                                  borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                }}
                              >
                                <Space size={6}>
                                  <UserOutlined style={{ color: "#7c3aed" }} />
                                  <span style={{ fontSize: 11, fontWeight: 600, color: isDark ? "#e2e8f0" : "#334155" }}>
                                    系统人设提示词 (System Prompt)
                                  </span>
                                </Space>
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
                                  fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
                                  background: isDark ? "#0d1117" : "#fafafa",
                                  color: isDark ? "#e2e8f0" : "#1e293b",
                                  padding: "8px 10px",
                                  margin: 0,
                                  maxHeight: 130,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                  lineHeight: 1.5,
                                }}
                              >
                                {systemPrompt}
                              </pre>
                            </div>
                          )}

                          {/* 2. 任务输入提示词 (User Prompt) */}
                          {promptText && (
                            <div
                              style={{
                                border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                borderRadius: 4,
                                overflow: "hidden",
                                background: isDark ? "#161b22" : "#ffffff",
                                boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  padding: "5px 10px",
                                  background: isDark ? "#21262d" : "#f1f5f9",
                                  borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                }}
                              >
                                <Space size={6}>
                                  <CodeOutlined style={{ color: "#2563eb" }} />
                                  <span style={{ fontSize: 11, fontWeight: 600, color: isDark ? "#e2e8f0" : "#334155" }}>
                                    任务分析输入 (User Prompt)
                                  </span>
                                  <span style={{ fontSize: 10, color: isDark ? "#8b949e" : "#64748b", fontWeight: "normal" }}>
                                    ({promptText.length} 字符)
                                  </span>
                                </Space>
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
                                  fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
                                  background: isDark ? "#0d1117" : "#fafafa",
                                  color: isDark ? "#e2e8f0" : "#1e293b",
                                  padding: "8px 10px",
                                  margin: 0,
                                  maxHeight: 160,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                  lineHeight: 1.5,
                                }}
                              >
                                {promptText}
                              </pre>
                            </div>
                          )}

                          {/* 3. 模型产物响应文本 (Model Response) */}
                          {completionText && (
                            <div
                              style={{
                                border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                borderRadius: 4,
                                overflow: "hidden",
                                background: isDark ? "#161b22" : "#ffffff",
                                boxShadow: "0 1px 2px rgba(0, 0, 0, 0.03)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  padding: "5px 10px",
                                  background: isDark ? "#21262d" : "#f1f5f9",
                                  borderBottom: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                                }}
                              >
                                <Space size={6}>
                                  <CheckCircleOutlined style={{ color: "#16a34a" }} />
                                  <span style={{ fontSize: 11, fontWeight: 600, color: isDark ? "#e2e8f0" : "#334155" }}>
                                    大模型返回结果 (Completion Response)
                                  </span>
                                </Space>
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
                                  fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
                                  background: isDark ? "#0d1117" : "#fafafa",
                                  color: isDark ? "#e2e8f0" : "#1e293b",
                                  padding: "8px 10px",
                                  margin: 0,
                                  maxHeight: 150,
                                  overflowY: "auto",
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                  lineHeight: 1.5,
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
