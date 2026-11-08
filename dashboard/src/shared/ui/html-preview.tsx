import { useEffect, useState } from "react";
import { LoadingState } from "./loading-state";

interface HtmlPreviewProps {
  title: string;
  html?: string;
  src?: string;
  sandbox: string;
  className?: string;
}

/** 页面内容立即可读；外链未完成时提示等待，不把网络等待伪装成空白。 */
export function HtmlPreview({ title, html, src, sandbox, className }: HtmlPreviewProps) {
  const [phase, setPhase] = useState<"loading" | "ready" | "slow" | "error">("loading");
  useEffect(() => {
    setPhase("loading");
    const timer = setTimeout(
      () => setPhase((value) => (value === "loading" ? "slow" : value)),
      20000,
    );
    return () => clearTimeout(timer);
  }, [html, src]);
  return (
    <div className="grid gap-2">
      {phase === "loading" && (
        <LoadingState className="text-sm text-muted-foreground">
          正在打开 HTML，外链素材可能需要稍等…
        </LoadingState>
      )}
      {phase === "slow" && (
        <p role="status" className="m-0 text-sm text-warning">
          页面仍在加载，部分外链素材可能较慢或不可达。可以先查看已显示的内容。
        </p>
      )}
      {phase === "error" && (
        <p role="alert" className="m-0 text-sm text-destructive">
          HTML 未能打开，请关闭预览后重试。
        </p>
      )}
      <iframe
        title={title}
        srcDoc={html || undefined}
        src={!html ? src : undefined}
        sandbox={sandbox}
        className={className}
        onLoad={() => setPhase("ready")}
        onError={() => setPhase("error")}
      />
    </div>
  );
}
