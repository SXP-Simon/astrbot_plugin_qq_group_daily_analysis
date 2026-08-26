import React from "react";
import { Collapse, Tabs, Tag, Space, Typography, Button, message, theme } from "antd";
import { FileTextOutlined, CopyOutlined } from "@ant-design/icons";
import { copyToClipboard } from "../../../shared/lib/clipboard";

const { Text } = Typography;

export interface PromptDetail {
  prompt?: string;
  system_prompt?: string;
  provider_id?: string;
}

interface PromptsInspectorProps {
  prompts?: Record<string, PromptDetail | string>;
}

export const PromptsInspector: React.FC<PromptsInspectorProps> = ({ prompts }) => {
  const { token } = theme.useToken();

  if (!prompts || typeof prompts !== "object" || Object.keys(prompts).length === 0) {
    return null;
  }

  const promptEntries = Object.entries(prompts);

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
                <FileTextOutlined style={{ color: "#1677ff" }} />
                <span style={{ fontWeight: 600, fontSize: 12 }}>
                  查看本次任务 LLM 实际提示词 (Prompts)
                </span>
                <Tag color="blue" style={{ fontSize: 10 }}>
                  {promptEntries.length} 个子任务
                </Tag>
              </Space>
            ),
            children: (
              <Tabs
                size="small"
                items={promptEntries.map(([analyzerName, pInfo]) => {
                  const isStr = typeof pInfo === "string";
                  const promptContent = isStr ? pInfo : pInfo?.prompt || JSON.stringify(pInfo);
                  const providerId = !isStr ? pInfo?.provider_id : undefined;

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
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            Provider: {providerId || "默认"} | 长度: {promptContent.length} 字符
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
                            wordBreak: "break-word",
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
  );
};
