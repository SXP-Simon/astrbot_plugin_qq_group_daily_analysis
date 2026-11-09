import { useState } from "react";
import type { BackupJsonValue } from "@/entities/plugin-data/model/configBackup";

export function JsonBackupTree({ label, value }: { label: string; value: BackupJsonValue }) {
  const [expanded, setExpanded] = useState(false);
  const compound = value !== null && typeof value === "object";
  const longString = typeof value === "string" && (value.length > 120 || value.includes("\n"));
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
  const entries: [string, BackupJsonValue][] = compound ? Object.entries(value) : [];
  const name = (
    <>
      <span className="break-all font-mono text-sm">{label}</span>{" "}
      <span className="text-xs text-muted-foreground">
        {type}
        {compound ? ` · ${entries.length} 项` : ""}
      </span>
    </>
  );
  if (!compound && !longString) {
    return (
      <div className="flex flex-wrap gap-x-3 gap-y-1 py-1.5 text-sm">
        <span>{name}</span>
        <code className="break-all">{JSON.stringify(value)}</code>
      </div>
    );
  }
  return (
    <details onToggle={(event) => setExpanded(event.currentTarget.open)} className="py-1.5">
      <summary className="cursor-pointer break-words rounded-sm focus-visible:outline-2 focus-visible:outline-ring">
        {name}
        {longString && (
          <span className="ml-2 text-xs text-muted-foreground">
            {String(value).length} 字符，展开查看
          </span>
        )}
      </summary>
      {expanded &&
        (compound ? (
          <div className="ml-2 border-l border-border pl-2 sm:ml-3 sm:pl-3">
            {entries.map(([key, child]) => (
              <JsonBackupTree
                key={key}
                label={Array.isArray(value) ? `[${key}]` : key}
                value={child}
              />
            ))}
          </div>
        ) : (
          <pre className="my-2 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 font-mono text-sm [overflow-wrap:anywhere]">
            {String(value)}
          </pre>
        ))}
    </details>
  );
}
