import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { message } from "antd";
import { deleteWordCloudFont, fetchWordCloudCatalog, fetchWordCloudSnapshots, previewWordCloud, previewWordCloudFont, renameWordCloudFont, restoreWordCloudFont, uploadWordCloudFont } from "../../../entities/wordcloud/api/wordCloudApi";
import { wordCloudOptionsSchema, type WordCloudCatalog, type WordCloudOptions, type WordCloudPreview, type WordCloudPreviewSource, type WordCloudSnapshot } from "../../../entities/wordcloud/model/types";
import { DENSITY_PRESETS, fitCandidates, measureWordCloudHtml, readableDraft, visualPatch, type DensityPreset, type RenderCounts } from "./wordCloudLayout";

export function useWordCloudEditor(value: Record<string, unknown> | undefined, onChange: (key: string, value: unknown) => void, onPatch: (patch: Record<string, unknown>) => void, scopeUmo?: string, protectedFonts: string[] = [], overrideKeys?: string[], disabled = false) {
  const [messageApi, messageContextHolder] = message.useMessage();
  const parsed = useMemo(() => wordCloudOptionsSchema.safeParse(value ?? {}), [value]);
  const options = useMemo(() => readableDraft(value), [value]);
  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!parsed.success) for (const issue of parsed.error.issues) {
      const key = String(issue.path[0] ?? "");
      errors[key] = issue.code === "custom" ? issue.message : `当前值 ${JSON.stringify(value?.[key])} 无效，请检查范围或格式`;
    }
    return errors;
  }, [parsed, value]);
  const validationError = Object.values(fieldErrors)[0] ?? "";
  const draftKey = JSON.stringify(value ?? {});
  const [sourceId, setSourceId] = useState("sample");
  const source = useMemo<WordCloudPreviewSource>(() => sourceId === "sample" ? { source: "sample", umo: scopeUmo } : { source: "snapshot", snapshot_id: sourceId, umo: scopeUmo }, [sourceId, scopeUmo]);
  const requestKey = JSON.stringify([draftKey, source]);
  const latestKey = useRef(requestKey);
  latestKey.current = requestKey;
  const callbacks = useRef({ onChange, onPatch });
  callbacks.current = { onChange, onPatch };
  const [catalog, setCatalog] = useState<WordCloudCatalog>({ templates: [], fonts: [] });
  const [catalogError, setCatalogError] = useState("");
  const [snapshots, setSnapshots] = useState<WordCloudSnapshot[]>([]);
  const [snapshotError, setSnapshotError] = useState("");
  const [snapshotsLoaded, setSnapshotsLoaded] = useState(false);
  const [metadata, setMetadata] = useState<WordCloudPreview["metadata"]>();
  const [htmlPreview, setHtmlPreview] = useState<{ html: string; width: number; height: number; id: number } | null>(null);
  const [previewState, setPreviewState] = useState<"loading" | "ready" | "error">("loading");
  const [previewError, setPreviewError] = useState("");
  const [counts, setCounts] = useState<RenderCounts | null>(null);
  const [image, setImage] = useState<{ url: string; key: string } | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fontBusy, setFontBusy] = useState(false);
  const [fontSample, setFontSample] = useState("");
  const [fontSampleError, setFontSampleError] = useState("");
  const [deletedFont, setDeletedFont] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [undoAction, setUndoAction] = useState<{ label: string; before: Record<string, unknown>; after: Record<string, unknown> } | null>(null);
  const [fitProgress, setFitProgress] = useState("");
  const [fitNotice, setFitNotice] = useState("");
  const fitController = useRef<AbortController | null>(null);
  const htmlSequence = useRef(0);
  const imageSequence = useRef(0);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; imageSequence.current += 1; fitController.current?.abort(); };
  }, []);

  useEffect(() => { setSourceId("sample"); }, [scopeUmo]);
  useEffect(() => { if (disabled) { fitController.current?.abort(); setFitProgress(""); } }, [disabled]);

  useEffect(() => {
    let active = true;
    fetchWordCloudCatalog().then((result) => {
      if (active) { setCatalog(result); setCatalogError(""); }
    }).catch((error: unknown) => {
      if (active) setCatalogError(error instanceof Error ? error.message : "读取模板和字体失败");
    });
    fetchWordCloudSnapshots().then((result) => {
      if (active) { setSnapshots(result); setSnapshotError(""); setSnapshotsLoaded(true); }
    }).catch((error: unknown) => {
      if (active) { setSnapshotError(error instanceof Error ? error.message : "读取群聊缓存失败"); setSnapshotsLoaded(true); }
    });
    return () => { active = false; };
  }, [refreshIndex]);

  useEffect(() => {
    let active = true;
    setFontSample("");
    setFontSampleError("");
    previewWordCloudFont(options.font).then((result) => { if (active) setFontSample(result.html); }).catch((error: unknown) => {
      if (active) setFontSampleError(error instanceof Error ? error.message : "字体样张加载失败");
    });
    return () => { active = false; };
  }, [options.font, refreshIndex]);

  useEffect(() => {
    fitController.current?.abort();
    fitController.current = null;
    setFitProgress("");
    const sequence = ++htmlSequence.current;
    let active = true;
    setPreviewState(validationError ? "error" : "loading");
    setPreviewError(validationError);
    setCounts(null);
    setMetadata(undefined);
    setHtmlPreview(null);
    imageSequence.current += 1;
    setImageLoading(false);
    setImageError("");
    const timer = window.setTimeout(() => {
      if (validationError) return;
      const snapshot = wordCloudOptionsSchema.parse(JSON.parse(draftKey) as unknown);
      previewWordCloud(snapshot, "html", source).then((result) => {
        if (!active || sequence !== htmlSequence.current || requestKey !== latestKey.current) return;
        setMetadata(result.metadata);
        setHtmlPreview({ html: result.html ?? "", width: snapshot.width, height: snapshot.height, id: sequence });
      }).catch((error: unknown) => {
        if (!active || sequence !== htmlSequence.current || requestKey !== latestKey.current) return;
        setPreviewState("error");
        setPreviewError(error instanceof Error ? error.message : "生成快速预览失败");
      });
    }, 350);
    return () => { active = false; window.clearTimeout(timer); };
  }, [draftKey, requestKey, source, validationError, refreshIndex]);

  useLayoutEffect(() => {
    if (!htmlPreview) return;
    const timer = window.setTimeout(() => {
      if (htmlPreview.id !== htmlSequence.current) return;
      setPreviewState("error");
      setPreviewError("字体或图片尚未就绪，请刷新预览后重试");
    }, 20000);
    const onMessage = (event: MessageEvent<unknown>) => {
      if (htmlPreview.id !== htmlSequence.current) return;
      if (event.source !== iframeRef.current?.contentWindow || !event.data || typeof event.data !== "object") return;
      const payload = event.data as Record<string, unknown>;
      if (payload.type !== "wordcloud-render-state" && payload.type !== "astrbot-wordcloud-ready") return;
      const state = payload.state ?? payload.status;
      if (state !== "ready" && state !== "error") return;
      window.clearTimeout(timer);
      setPreviewState(state);
      const error = payload.error ?? payload.message;
      setPreviewError(state === "error" ? (typeof error === "string" ? error : "字体、图片或排版加载失败") : "");
      const placed = payload.shown ?? payload.placed;
      if (typeof placed === "number" && typeof payload.total === "number") setCounts({ placed, total: payload.total });
    };
    window.addEventListener("message", onMessage);
    return () => { window.clearTimeout(timer); window.removeEventListener("message", onMessage); };
  }, [htmlPreview]);

  const renderImage = useCallback(async () => {
    if (validationError) return;
    const sequence = ++imageSequence.current;
    setImageLoading(true);
    setImageError("");
    try {
      const snapshot = wordCloudOptionsSchema.parse(JSON.parse(draftKey) as unknown);
      const result = await previewWordCloud(snapshot, "image", source);
      if (mounted.current && sequence === imageSequence.current && requestKey === latestKey.current) setImage({ url: result.image ?? "", key: requestKey });
    } catch (error: unknown) {
      if (mounted.current && sequence === imageSequence.current && requestKey === latestKey.current) setImageError(error instanceof Error ? error.message : "T2I 图片预览失败");
    } finally {
      if (mounted.current && sequence === imageSequence.current) setImageLoading(false);
    }
  }, [draftKey, requestKey, source, validationError]);

  const applyVisualAction = useCallback((label: string, patch: Record<string, unknown>) => {
    const after = visualPatch(patch);
    const before = Object.fromEntries(Object.keys(after).map((key) => [key, overrideKeys && !overrideKeys.includes(key) ? undefined : options[key]]));
    setUndoAction({ label, before, after });
    callbacks.current.onPatch(after);
  }, [options, overrideKeys]);

  const undo = useCallback(() => {
    if (!undoAction) return;
    const patch = Object.fromEntries(Object.entries(undoAction.before).filter(([key]) => JSON.stringify(options[key]) === JSON.stringify(undoAction.after[key])));
    callbacks.current.onPatch(patch);
    setUndoAction(null);
    setFitNotice("");
  }, [undoAction, options]);

  const fitMore = useCallback(async () => {
    if (!parsed.success || !counts || previewState !== "ready") return;
    fitController.current?.abort();
    const controller = new AbortController();
    fitController.current = controller;
    const initial = parsed.data;
    let best = initial;
    let bestCounts = counts;
    setFitNotice("");
    try {
      const candidates = fitCandidates(initial);
      for (const [index, candidate] of candidates.entries()) {
        if (controller.signal.aborted || requestKey !== latestKey.current) return;
        if (bestCounts.placed >= bestCounts.total) break;
        setFitProgress(`正在尝试 ${index + 1} / ${candidates.length}…`);
        const rendered = await previewWordCloud(candidate, "html", source);
        if (controller.signal.aborted || requestKey !== latestKey.current) return;
        const measured = await measureWordCloudHtml(rendered.html ?? "", candidate, controller.signal);
        if (controller.signal.aborted || requestKey !== latestKey.current) return;
        if (measured.placed > bestCounts.placed) { best = candidate; bestCounts = measured; }
      }
      if (!mounted.current || controller.signal.aborted || requestKey !== latestKey.current) return;
      if (best !== initial) {
        applyVisualAction("自动紧凑调整", { word_spacing: best.word_spacing, min_font_size: best.min_font_size, max_font_size: best.max_font_size });
        setFitNotice(`已从 ${counts.placed} 个增加至 ${bestCounts.placed} 个词，可撤销本次调整。`);
      } else setFitNotice("已完成有限尝试，当前参数下未容纳更多词，保留原设置。可增加画布尺寸。");
    } catch (error: unknown) {
      if (mounted.current && !controller.signal.aborted && requestKey === latestKey.current) setFitNotice(error instanceof Error ? error.message : "自动调整失败，原设置已保留");
    } finally {
      if (mounted.current && fitController.current === controller) { setFitProgress(""); fitController.current = null; }
    }
  }, [parsed, counts, previewState, requestKey, source, applyVisualAction]);

  const uploadFont = useCallback(async (file: File) => {
    if (!/\.(woff2?|ttf|otf)$/i.test(file.name)) { messageApi.error("请选择 WOFF2、WOFF、TTF 或 OTF 字体"); return false; }
    if (file.size > 20 * 1024 * 1024) { messageApi.error("字体文件不能超过 20 MB"); return false; }
    setUploading(true);
    try {
      const font = await uploadWordCloudFont(file);
      if (mounted.current) {
        setCatalog((current) => ({ ...current, fonts: [...current.fonts.filter((item) => item.id !== font.id), font] }));
        if (requestKey === latestKey.current) callbacks.current.onChange("font", font.id);
        messageApi.success("字体已上传，保存配置后应用于发送的词云");
      }
    } catch (error: unknown) { if (mounted.current) messageApi.error(error instanceof Error ? error.message : "上传字体失败"); }
    finally { if (mounted.current) setUploading(false); }
    return false;
  }, [messageApi, requestKey]);

  const renameFont = useCallback(async (id: string, label: string) => {
    if (!label.trim()) { messageApi.error("请输入字体名称"); return false; }
    setFontBusy(true);
    try {
      await renameWordCloudFont(id, label.trim());
      if (mounted.current) { setRefreshIndex((index) => index + 1); messageApi.success("字体名称已更新"); }
      return true;
    } catch (error: unknown) { if (mounted.current) messageApi.error(error instanceof Error ? error.message : "重命名失败"); return false; }
    finally { if (mounted.current) setFontBusy(false); }
  }, [messageApi]);

  const deleteFont = useCallback(async (id: string) => {
    if (id === options.font || protectedFonts.includes(id)) { messageApi.error("当前草稿正在使用此字体，请先修改全局或群级字体并保存，再删除"); return; }
    setFontBusy(true);
    try {
      await deleteWordCloudFont(id);
      if (mounted.current) { setDeletedFont(id); setRefreshIndex((index) => index + 1); messageApi.success("字体已移入回收存档，可以撤销删除"); }
    } catch (error: unknown) { if (mounted.current) messageApi.error(error instanceof Error ? error.message : "删除字体失败"); }
    finally { if (mounted.current) setFontBusy(false); }
  }, [options.font, protectedFonts, messageApi]);

  const restoreFont = useCallback(async () => {
    if (!deletedFont) return;
    setFontBusy(true);
    try {
      await restoreWordCloudFont(deletedFont);
      if (mounted.current) { setDeletedFont(null); setRefreshIndex((index) => index + 1); messageApi.success("字体已恢复"); }
    } catch (error: unknown) { if (mounted.current) messageApi.error(error instanceof Error ? error.message : "恢复字体失败"); }
    finally { if (mounted.current) setFontBusy(false); }
  }, [deletedFont, messageApi]);

  const update = <K extends keyof WordCloudOptions>(key: K, next: WordCloudOptions[K]) => onChange(String(key), next);
  return {
    options, update, validationError, fieldErrors, catalog, catalogError, htmlPreview, iframeRef,
    previewState, previewError, counts, image: image?.key === requestKey ? image.url : null,
    imageLoading, imageError, uploading, renderImage, uploadFont, messageContextHolder,
    snapshots: snapshots.filter((item) => !scopeUmo || item.umo === scopeUmo), snapshotError, snapshotsLoaded, sourceId, setSourceId, metadata,
    fontSample, fontSampleError, fontBusy, renameFont, deleteFont, deletedFont, restoreFont,
    applyPreset: (preset: DensityPreset) => applyVisualAction("密度预设", DENSITY_PRESETS[preset]),
    restoreTemplate: () => { const defaults = catalog.templates.find((item) => item.name === options.template)?.defaults; if (defaults) applyVisualAction("模板默认外观", defaults); },
    undoLabel: undoAction?.label, undo, fitMore, fitProgress, fitNotice,
    cancelFit: () => { fitController.current?.abort(); setFitProgress(""); },
    refresh: () => setRefreshIndex((index) => index + 1),
  };
}
