import React from "react";
import { cn } from "../lib/cn";

interface MarkdownHintProps {
  content: string;
  style?: React.CSSProperties;
  className?: string;
}

export const MarkdownHint: React.FC<MarkdownHintProps> = ({ content, style, className }) => {
  if (!content) return null;

  // 拆分常见 Markdown 语法单元：[链接文本](url)、`行内代码`、**粗体**、换行符
  const tokenRegex = /(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*|\n)/g;
  const parts = content.split(tokenRegex);

  return (
    <span className={cn("[overflow-wrap:anywhere]", className)} style={style}>
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
              className="break-all font-medium text-secondary-ink underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-ring"
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
              className="mx-0.5 rounded border border-solid border-secondary-line bg-secondary-soft px-1 py-px font-mono text-[0.92em] text-secondary-ink"
            >
              {codeMatch[1]}
            </code>
          );
        }

        // 3. 解析粗体 **文本**
        const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
        if (boldMatch) {
          return (
            <strong key={index} className="font-medium text-foreground">
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
