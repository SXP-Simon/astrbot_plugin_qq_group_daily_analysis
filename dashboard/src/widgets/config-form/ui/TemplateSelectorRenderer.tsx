import { LoadingState } from "../../../shared/ui/loading-state";
import { useEffect, useMemo, useState } from "react";
import {
  IconCheck,
  IconDownload,
  IconEye,
  IconLayoutGrid,
  IconPhoto,
  IconTrash,
} from "@tabler/icons-react";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../entities/config/model/renderingConfig";
import {
  KNOWN_TEMPLATES,
  supportsTemplate,
  templateCapabilities,
  type TemplateRequirements,
} from "../../../entities/report/model/templates";
import { useReportTemplates } from "../../../entities/report/model/useReportTemplates";
import { useTemplatePreview } from "../../../entities/report/model/useTemplatePreview";
import { TemplateInstallModal } from "../../../features/install-template/ui/TemplateInstallModal";
import { TemplateUninstallModal } from "../../../features/install-template/ui/TemplateUninstallModal";
import { Alert } from "../../../shared/ui/alert";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogTitle } from "../../../shared/ui/dialog";
import { ImagePreview } from "../../../shared/ui/image-preview";
import { SearchSelect } from "../../../shared/ui/search-select";

interface TemplateSelectorRendererProps {
  cdnBaseUrl?: string | null;
  value: unknown;
  requirements?: TemplateRequirements;
  options?: unknown[];
  defaultValue?: unknown;
  onChange: (value: string) => void;
}

/** 缩略图的加载与地址来自实体模型，点击入口同时支持键盘。 */
function TemplateThumbnail({
  id,
  name,
  custom,
  cdnBaseUrl,
  compact,
  onPreview,
}: {
  id: string;
  name: string;
  custom: boolean;
  cdnBaseUrl: string | null;
  compact?: boolean;
  onPreview: () => void;
}) {
  const preview = useTemplatePreview(id, custom, cdnBaseUrl);
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <button
      type="button"
      aria-label={`预览 ${name}`}
      onClick={onPreview}
      className={`${compact ? "h-28 w-20 shrink-0" : "h-48 w-full"} relative flex cursor-zoom-in items-center justify-center overflow-hidden rounded-xl border border-solid border-border bg-muted/40 p-0 text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring`}
    >
      {preview.src && failed !== preview.src ? (
        <img
          src={preview.src}
          alt={name}
          loading="lazy"
          className="h-full w-full object-cover object-top"
          onError={() => setFailed(preview.src)}
        />
      ) : (
        <span className="flex flex-col items-center gap-2 p-2 text-xs">
          <IconPhoto aria-hidden="true" />
          <span>{preview.loading ? "读取预览…" : "暂无预览图"}</span>
        </span>
      )}
      <span className="absolute bottom-0 right-0 flex items-center gap-1 rounded-tl-lg bg-card/95 px-2 py-1 text-xs text-foreground">
        <IconEye size={14} aria-hidden="true" />
        预览
      </span>
    </button>
  );
}

export function TemplateSelectorRenderer({
  cdnBaseUrl = DEFAULT_TEMPLATE_CDN_BASE_URL,
  value,
  requirements,
  defaultValue,
  onChange,
}: TemplateSelectorRendererProps) {
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [installOpen, setInstallOpen] = useState(false);
  const [uninstallOpen, setUninstallOpen] = useState(false);
  const { templates: remoteTemplates, loading, ready, error, refresh } = useReportTemplates();
  const currentTemplate =
    typeof value === "string" && value
      ? value
      : typeof defaultValue === "string" && defaultValue
        ? defaultValue
        : "HatsuneMiku";
  useEffect(() => {
    setPreviewId(null);
  }, [currentTemplate]);
  const galleryItems = useMemo(
    () =>
      remoteTemplates
        .filter((item) => supportsTemplate(item, requirements))
        .map((item) => {
          const known = KNOWN_TEMPLATES.find((entry) => entry.key === item.id);
          return {
            key: item.id,
            custom: Boolean(item.is_custom),
            name: item.display_name || known?.name || item.label || item.id,
            description: item.desc || known?.desc || "",
            tag: item.tag || known?.tag || "",
            capabilities: templateCapabilities(item),
          };
        }),
    [remoteTemplates, requirements],
  );
  const current = galleryItems.find((item) => item.key === currentTemplate);
  const previewIndex = galleryItems.findIndex((item) => item.key === previewId);
  const previewItem = galleryItems[previewIndex];
  useEffect(() => {
    if (previewId && !galleryItems.some((item) => item.key === previewId)) setPreviewId(null);
  }, [galleryItems, previewId]);
  const preview = useTemplatePreview(
    previewItem?.key ?? "",
    previewItem?.custom ?? false,
    cdnBaseUrl,
    Boolean(previewItem),
  );
  const previewDialog = previewItem ? (
    <ImagePreview
      key={previewItem.key}
      src={preview.src}
      loading={preview.loading}
      error={preview.error}
      title={`模板预览 · ${previewItem.name}`}
      position={`${previewIndex + 1} / ${galleryItems.length}`}
      onPrevious={
        galleryOpen && previewIndex > 0
          ? () => setPreviewId(galleryItems[previewIndex - 1].key)
          : undefined
      }
      onNext={
        galleryOpen && previewIndex + 1 < galleryItems.length
          ? () => setPreviewId(galleryItems[previewIndex + 1].key)
          : undefined
      }
      onClose={() => setPreviewId(null)}
    />
  ) : null;

  return (
    <div className="grid min-w-0 gap-3">
      {error && (
        <Alert variant="destructive">
          {error}
          <Button size="sm" variant="outline" className="ml-2" onClick={() => void refresh()}>
            重试
          </Button>
        </Alert>
      )}
      {loading && (
        <LoadingState className="m-0 text-sm text-muted-foreground">正在读取模板列表…</LoadingState>
      )}
      {ready && !remoteTemplates.length && (
        <p className="m-0 text-sm text-muted-foreground">暂无可用模板，请安装模板或刷新列表。</p>
      )}
      {ready && !current && (
        <Alert variant="warning">
          当前主题不支持所选渲染引擎或输出格式，请选择兼容主题。切换不会自动覆盖你的配置。
        </Alert>
      )}
      {cdnBaseUrl === null && (
        <Alert variant="destructive">
          CDN 地址没填对，请先到「图片渲染策略」改一下，再来看模板预览。
        </Alert>
      )}
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="min-w-0 basis-60 grow">
          <SearchSelect
            label="报告模板"
            value={currentTemplate}
            disabled={!ready}
            virtual
            options={galleryItems.map((item) => ({
              value: item.key,
              label: `${item.name} [${item.capabilities.join(" / ")}]`,
            }))}
            onChange={onChange}
          />
        </div>
        <Button variant="outline" disabled={!current} onClick={() => setPreviewId(currentTemplate)}>
          <IconEye aria-hidden="true" />
          预览当前效果
        </Button>
        <Button variant="outline" onClick={() => setGalleryOpen(true)}>
          <IconLayoutGrid aria-hidden="true" />
          浏览全部模板画廊
        </Button>
        <Button variant="outline" onClick={() => setInstallOpen(true)}>
          <IconDownload aria-hidden="true" />
          安装模板
        </Button>
        <Button variant="outline" onClick={() => setUninstallOpen(true)}>
          <IconTrash aria-hidden="true" />
          卸载模板
        </Button>
      </div>
      {current && (
        <div className="flex items-center gap-4 rounded-xl bg-muted/40 p-3">
          <TemplateThumbnail
            id={current.key}
            name={current.name}
            custom={current.custom}
            cdnBaseUrl={cdnBaseUrl}
            compact
            onPreview={() => setPreviewId(current.key)}
          />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{current.name}</span>
              {current.tag && (
                <span className="rounded-md bg-secondary px-2 py-1 text-xs text-secondary-foreground">
                  {current.tag}
                </span>
              )}
            </div>
            <p className="mb-0 mt-2 text-sm leading-relaxed text-muted-foreground">
              {current.description}
            </p>
          </div>
        </div>
      )}
      <TemplateInstallModal
        open={installOpen}
        onClose={() => setInstallOpen(false)}
        onInstalled={() => void refresh()}
      />
      <TemplateUninstallModal
        open={uninstallOpen}
        onClose={() => setUninstallOpen(false)}
        onUninstalled={(name) => {
          void refresh();
          if (currentTemplate === name) onChange("HatsuneMiku");
        }}
      />
      <Dialog
        open={galleryOpen}
        onOpenChange={(open) => {
          if (!previewItem) setGalleryOpen(open);
        }}
      >
        <DialogContent className="max-w-5xl" aria-describedby={undefined}>
          <DialogTitle>报告模板视觉样式画廊</DialogTitle>
          {!galleryItems.length && (
            <p className="text-sm text-muted-foreground">没有符合当前渲染方式的模板。</p>
          )}
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {galleryItems.map((item) => (
              <article
                key={item.key}
                aria-label={item.name}
                className={`flex min-w-0 flex-col gap-3 rounded-xl border border-solid p-3 ${item.key === currentTemplate ? "border-primary bg-primary/10" : "border-border bg-muted/20"}`}
              >
                <TemplateThumbnail
                  id={item.key}
                  name={item.name}
                  custom={item.custom}
                  cdnBaseUrl={cdnBaseUrl}
                  onPreview={() => setPreviewId(item.key)}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="m-0 break-words text-base font-medium">{item.name}</h3>
                  {item.custom && (
                    <span className="rounded-md bg-secondary-soft px-2 py-1 text-xs text-secondary-ink">
                      自定义
                    </span>
                  )}
                </div>
                {!!item.capabilities.length && (
                  <p className="m-0 text-xs text-muted-foreground">
                    {item.capabilities.join(" · ")}
                  </p>
                )}
                {item.tag && <span className="text-xs text-muted-foreground">{item.tag}</span>}
                <p className="m-0 grow text-sm leading-relaxed text-muted-foreground">
                  {item.description}
                </p>
                <Button
                  className="self-end"
                  variant={item.key === currentTemplate ? "secondary" : "default"}
                  disabled={item.key === currentTemplate}
                  onClick={() => {
                    onChange(item.key);
                    setGalleryOpen(false);
                  }}
                >
                  {item.key === currentTemplate ? (
                    <>
                      <IconCheck aria-hidden="true" />
                      当前使用中
                    </>
                  ) : (
                    "应用此模板"
                  )}
                </Button>
              </article>
            ))}
          </div>
          {galleryOpen && previewDialog}
        </DialogContent>
      </Dialog>
      {!galleryOpen && previewDialog}
    </div>
  );
}
