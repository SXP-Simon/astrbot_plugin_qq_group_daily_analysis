import React from "react";
import { Collapse, theme } from "antd";
import { CodeOutlined } from "@ant-design/icons";

interface SpanPayloadViewerProps {
  payload?: Record<string, unknown>;
}

export const SpanPayloadViewer: React.FC<SpanPayloadViewerProps> = ({ payload }) => {
  const { token } = theme.useToken();

  if (!payload || Object.keys(payload).length === 0) {
    return null;
  }

  // 过滤掉已在上方通过专属可视化卡片/徽章呈现的冗余大字段，避免重复堆叠
  const displayPayload = { ...payload };
  delete displayPayload.prompts;
  delete displayPayload.llm_attempts;
  delete displayPayload.render_attempts;
  delete displayPayload.subtask_errors;

  if (Object.keys(displayPayload).length === 0) {
    return null;
  }

  return (
    <div style={{ marginTop: 6 }}>
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: "raw_payload",
            label: (
              <span style={{ fontSize: 11, color: token.colorTextSecondary }}>
                <CodeOutlined style={{ marginRight: 4 }} />
                查看底层阶段原始 Payload (JSON)
              </span>
            ),
            children: (
              <pre
                style={{
                  fontSize: 11,
                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
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
                {JSON.stringify(displayPayload, null, 2)}
              </pre>
            ),
          },
        ]}
      />
    </div>
  );
};
