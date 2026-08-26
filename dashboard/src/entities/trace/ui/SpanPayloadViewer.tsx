import React from "react";
import { theme } from "antd";

interface SpanPayloadViewerProps {
  payload?: Record<string, unknown>;
}

export const SpanPayloadViewer: React.FC<SpanPayloadViewerProps> = ({ payload }) => {
  const { token } = theme.useToken();

  if (!payload || Object.keys(payload).length === 0) {
    return null;
  }

  // Filter out internal/duplicate fields that are already displayed in specialized badges
  const displayPayload = { ...payload };
  delete displayPayload.prompts;

  if (Object.keys(displayPayload).length === 0) {
    return null;
  }

  return (
    <div>
      <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 4 }}>
        阶段调用参数与执行产物明细：
      </div>
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
    </div>
  );
};
