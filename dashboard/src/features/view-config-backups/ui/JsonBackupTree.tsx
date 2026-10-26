import { useState } from "react";
import { Tag, Typography } from "antd";
import type { BackupJsonValue } from "../../../entities/plugin-data/model/configBackup";

export function JsonBackupTree({
  label,
  value,
}: {
  label: string;
  value: BackupJsonValue;
}) {
  const [expanded, setExpanded] = useState(false);
  const compound = value !== null && typeof value === "object";
  const longString =
    typeof value === "string" && (value.length > 120 || value.includes("\n"));
  const type =
    value === null
      ? "null"
      : Array.isArray(value)
      ? "数组"
      : compound
      ? "对象"
      : typeof value === "string"
      ? "字符串"
      : typeof value === "number"
      ? "数字"
      : "布尔值";
  const entries: [string, BackupJsonValue][] = compound
    ? Object.entries(value)
    : [];
  const name = (
    <>
      <Typography.Text strong style={{ overflowWrap: "anywhere" }}>
        {label}
      </Typography.Text>{" "}
      <Tag>
        {type}
        {compound ? ` · ${entries.length} 项` : ""}
      </Tag>
    </>
  );

  if (!compound && !longString) {
    return (
      <div style={{ padding: "5px 0", overflowWrap: "anywhere" }}>
        {name}
        <code>{JSON.stringify(value)}</code>
      </div>
    );
  }
  return (
    <details
      onToggle={(event) => setExpanded(event.currentTarget.open)}
      style={{ padding: "5px 0" }}
    >
      <summary style={{ cursor: "pointer", overflowWrap: "anywhere" }}>
        {name}
        {longString && (
          <Typography.Text type="secondary">
            {String(value).length} 字符，展开查看
          </Typography.Text>
        )}
      </summary>
      {expanded &&
        (compound ? (
          <div
            style={{
              marginLeft: 16,
              paddingLeft: 12,
              borderLeft: "1px solid var(--ant-color-border, #d9d9d9)",
            }}
          >
            {entries.map(([key, child]) => (
              <JsonBackupTree
                key={key}
                label={Array.isArray(value) ? `[${key}]` : key}
                value={child}
              />
            ))}
          </div>
        ) : (
          <pre
            style={{
              margin: "8px 0",
              padding: 12,
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              fontFamily: "ui-monospace, monospace",
            }}
          >
            {String(value)}
          </pre>
        ))}
    </details>
  );
}
