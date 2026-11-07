import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconCopy } from "@tabler/icons-react";
import { copyToClipboard } from "../lib/clipboard";
import { Button } from "./button";

export function CopyButton({
  text,
  label,
  children = "复制",
}: {
  text: string;
  label: string;
  children?: ReactNode;
}) {
  const [result, setResult] = useState<"success" | "failure" | null>(null);
  const [copying, setCopying] = useState(false);
  const request = useRef(0),
    pending = useRef(false);
  useEffect(() => {
    const sequence = request;
    sequence.current++;
    pending.current = false;
    setCopying(false);
    setResult(null);
    return () => {
      sequence.current++;
    };
  }, [text]);
  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        aria-label={label}
        disabled={copying}
        onClick={async () => {
          if (pending.current) return;
          pending.current = true;
          setCopying(true);
          setResult(null);
          const sequence = request.current;
          const copied = await copyToClipboard(text);
          if (sequence !== request.current) return;
          pending.current = false;
          setCopying(false);
          setResult(copied ? "success" : "failure");
        }}
      >
        <IconCopy aria-hidden="true" />
        {copying ? "正在复制…" : children}
      </Button>
      <span
        role="status"
        className={result === "failure" ? "text-xs text-warning" : "text-xs text-success"}
      >
        {result === "success" ? "已复制" : result === "failure" ? "复制失败，请手动选择文字。" : ""}
      </span>
    </span>
  );
}
