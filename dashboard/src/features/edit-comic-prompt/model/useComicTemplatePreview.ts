import { useEffect, useRef, useState } from "react";
import { fetchComicTemplatePreview, type ComicPreviewVariant } from "../api/comicTemplateApi";
import type { ComicPromptTemplate } from "./useComicPromptEditor";

interface PreviewState {
  key: string;
  status: "loading" | "ready" | "empty" | "error";
  src?: string;
  error?: string;
}

/** 可见时才加载画廊图片；切换和卸载后忽略已过期的响应。 */
export function useComicTemplatePreview(template: ComicPromptTemplate | undefined, eager = false, variant: ComicPreviewVariant = "thumbnail") {
  const targetRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<PreviewState | null>(null);
  const id = template?.id;
  const key = `${id}:${variant}`;
  const hasPreview = Boolean(template?.preview);
  const enabled = eager || visible;

  useEffect(() => {
    if (eager || !hasPreview || !targetRef.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: "120px" });
    observer.observe(targetRef.current);
    return () => observer.disconnect();
  }, [eager, hasPreview]);

  useEffect(() => {
    if (!enabled || !id || !hasPreview) return;
    let cancelled = false;
    setState({ key, status: "loading" });
    const timeout = window.setTimeout(() => {
      cancelled = true;
      setState({ key, status: "error", error: "示例图加载超时，请重试" });
    }, 15000);
    void fetchComicTemplatePreview(id, variant, revision > 0).then((src) => {
      window.clearTimeout(timeout);
      if (!cancelled) setState(src ? { key, status: "ready", src } : { key, status: "empty" });
    }).catch((error: unknown) => {
      window.clearTimeout(timeout);
      if (!cancelled) setState({
        key,
        status: "error",
        error: error instanceof Error ? error.message : "示例图加载失败",
      });
    });
    return () => { cancelled = true; window.clearTimeout(timeout); };
  }, [enabled, id, key, hasPreview, revision, variant]);

  const current = id && hasPreview && state?.key === key ? state : null;
  return {
    targetRef,
    status: !hasPreview ? "empty" : current?.status ?? "loading",
    src: current?.src,
    error: current?.error,
    retry: () => setRevision((previous) => previous + 1),
    imageFailed: () => {
      if (id) setState({ key, status: "error", error: "示例图无法显示，请重新加载" });
    },
  };
}
