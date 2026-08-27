import React from "react";
import { useTheme } from "../lib/useTheme";

interface MarkdownHintProps {
  content: string;
  style?: React.CSSProperties;
  className?: string;
}

export const MarkdownHint: React.FC<MarkdownHintProps> = ({
  content,
  style,
  className,
}) => {
  const { isDark } = useTheme();

  if (!content) return null;

  // 拆分常见 Markdown 语法单元：[链接文本](url)、`行内代码`、**粗体**、换行符
  const tokenRegex = /(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*|\n)/g;
  const parts = content.split(tokenRegex);

  return (
    <span className={className} style={style}>
      {parts.map((part, index) => {
        if (!part) return null;

        // 1. 解析 Markdown 超链接 [文本](URL)
        const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (linkMatch) {
          const [, linkText, linkUrl] = linkMatch;
          return (
            <a
              key={index}
              href={linkUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: isDark ? "#60a5fa" : "#2563eb",
                textDecoration: "underline",
                wordBreak: "break-all",
                fontWeight: 500,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {linkText}
            </a>
          );
        }

        // 2. 解析行内代码 `代码片段`
        const codeMatch = part.match(/^`([^`]+)`$/);
        if (codeMatch) {
          return (
            <code
              key={index}
              style={{
                fontFamily:
                  "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: "0.92em",
                padding: "1px 5px",
                margin: "0 2px",
                borderRadius: 3,
                background: isDark
                  ? "rgba(255, 255, 255, 0.08)"
                  : "rgba(0, 0, 0, 0.06)",
                color: isDark ? "#fca5a5" : "#b91c1c",
                border: `1px solid ${
                  isDark ? "rgba(255, 255, 255, 0.12)" : "rgba(0, 0, 0, 0.08)"
                }`,
              }}
            >
              {codeMatch[1]}
            </code>
          );
        }

        // 3. 解析粗体 **文本**
        const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
        if (boldMatch) {
          return (
            <strong
              key={index}
              style={{
                fontWeight: 600,
                color: isDark ? "#f3f4f6" : "#111827",
              }}
            >
              {boldMatch[1]}
            </strong>
          );
        }

        // 4. 换行
        if (part === "\n") {
          return <br key={index} />;
        }

        // 普通文本
        return <span key={index}>{part}</span>;
      })}
    </span>
  );
};
