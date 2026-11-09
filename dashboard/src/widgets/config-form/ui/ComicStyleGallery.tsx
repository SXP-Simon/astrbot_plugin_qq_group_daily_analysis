import { useState } from "react";
import { IconPhoto } from "@tabler/icons-react";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../entities/config/model/renderingConfig";
import {
  GITHUB_REPO_BRANCH,
  GITHUB_REPO_NAME,
  GITHUB_REPO_OWNER,
} from "../../../entities/report/model/templates";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import { ImagePreview } from "../../../shared/ui/image-preview";
import { comicPresets } from "../../../entities/comic/model/comicPresets";

function ComicStyleThumbnail({ name, src }: { name: string; src?: string }) {
  const [failed, setFailed] = useState<string>();
  return src && failed !== src ? (
    <img
      src={src}
      alt={name}
      loading="lazy"
      className="h-full w-full object-cover object-top"
      onError={() => setFailed(src)}
    />
  ) : (
    <span className="flex flex-col items-center gap-2 text-xs text-muted-foreground">
      <IconPhoto aria-hidden="true" />
      暂无预览图
    </span>
  );
}

export function ComicStyleGallery({
  cdnBaseUrl = DEFAULT_TEMPLATE_CDN_BASE_URL,
  selected,
  onSelect,
}: {
  cdnBaseUrl?: string | null;
  selected?: unknown;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const getComicStylePreviewUrl = (presetId: string, variant: "thumbnail" | "preview") => {
    if (cdnBaseUrl === null) return undefined;
    const file = `${presetId}/${variant}.webp`;
    const repository = `${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}@${GITHUB_REPO_BRANCH}`;
    return `${cdnBaseUrl}/gh/${repository}/assets/comic_previews/${file}`;
  };
  const selectedPreview = comicPresets.find(({ id }) => id === preview);
  const cdnError = cdnBaseUrl === null ? "CDN 地址无效，请先修改图片渲染策略。" : undefined;
  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
        浏览漫画风格
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90dvh] max-w-5xl overflow-y-auto">
          <DialogTitle>漫画风格</DialogTitle>
          <DialogDescription>示例仅供参考，实际效果取决于群聊内容和绘图模型。</DialogDescription>
          {cdnError && (
            <p role="alert" className="m-0 text-sm text-destructive">
              {cdnError}
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {comicPresets.map((preset) => (
              <article
                key={preset.id}
                className="min-w-0 space-y-2 rounded-xl border border-border p-3"
              >
                <button
                  type="button"
                  className="flex h-36 w-full cursor-zoom-in items-center justify-center overflow-hidden rounded-lg bg-muted"
                  aria-label={`预览 ${preset.name}`}
                  onClick={() => setPreview(preset.id)}
                >
                  <ComicStyleThumbnail
                    name={preset.name}
                    src={getComicStylePreviewUrl(preset.id, "thumbnail")}
                  />
                </button>
                <p className="m-0 text-sm font-medium">{preset.name}</p>
                <p className="m-0 text-sm text-muted-foreground">{preset.description}</p>
                <Button
                  type="button"
                  size="sm"
                  variant={selected === preset.id ? "outline" : "default"}
                  disabled={selected === preset.id}
                  aria-label={`选用 ${preset.name}`}
                  onClick={() => {
                    onSelect(preset.id);
                    setOpen(false);
                  }}
                >
                  {selected === preset.id ? "当前风格" : "选用此风格"}
                </Button>
              </article>
            ))}
          </div>
        </DialogContent>
      </Dialog>
      {selectedPreview && (
        <ImagePreview
          src={getComicStylePreviewUrl(selectedPreview.id, "preview") ?? null}
          title={selectedPreview.name}
          error={cdnError}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}
