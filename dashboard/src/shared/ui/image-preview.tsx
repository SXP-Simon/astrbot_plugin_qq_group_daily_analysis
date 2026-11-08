import { useEffect, useState } from "react";
import {
  IconArrowLeft,
  IconArrowRight,
  IconRotateClockwise,
  IconZoomIn,
  IconZoomOut,
} from "@tabler/icons-react";
import { Button } from "./button";
import { Dialog, DialogContent, DialogTitle } from "./dialog";

interface ImagePreviewProps {
  src: string | null;
  title: string;
  loading?: boolean;
  error?: string;
  position?: string;
  onPrevious?: () => void;
  onNext?: () => void;
  onClose: () => void;
}

/** 图片查看只处理展示状态，地址读取和图库选择仍由调用方管理。 */
export function ImagePreview({
  src,
  title,
  loading,
  error,
  position,
  onPrevious,
  onNext,
  onClose,
}: ImagePreviewProps) {
  const [viewport, setViewport] = useState<HTMLDivElement | null>(null);
  const [bounds, setBounds] = useState({ width: 0, height: 0 });
  const [natural, setNatural] = useState({ width: 0, height: 0 });
  const [loaded, setLoaded] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [originalSize, setOriginalSize] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [flipped, setFlipped] = useState(false);
  useEffect(() => {
    setZoom(1);
    setOriginalSize(false);
    setRotation(0);
    setFlipped(false);
    setNatural({ width: 0, height: 0 });
    setLoaded(null);
    setFailed(null);
  }, [src]);
  useEffect(() => {
    const element = viewport;
    if (!element) return;
    const measure = () => setBounds({ width: element.clientWidth, height: element.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [viewport]);
  const ready = Boolean(src && loaded === src && !error && failed !== src);
  const imageError =
    error || (src && failed === src ? "图片未能加载，请检查资源地址后重新预览。" : "");
  const fit =
    natural.width && natural.height
      ? Math.min(
          1,
          Math.max(1, bounds.width - 32) / natural.width,
          Math.max(1, bounds.height - 32) / natural.height,
        )
      : 1;
  const scale = (originalSize ? 1 : fit) * zoom;
  const width = natural.width * scale;
  const height = natural.height * scale;
  const rotated = rotation % 180 !== 0;

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="max-w-6xl"
        aria-describedby={undefined}
        onEscapeKeyDown={(event) => event.stopPropagation()}
      >
        <DialogTitle className="break-words">{title}</DialogTitle>
        <div className="flex flex-wrap items-center gap-2" aria-label="图片操作">
          {(onPrevious || onNext) && (
            <>
              <Button variant="outline" size="sm" disabled={!onPrevious} onClick={onPrevious}>
                <IconArrowLeft aria-hidden="true" />
                上一张
              </Button>
              <span className="text-sm text-muted-foreground">{position}</span>
              <Button variant="outline" size="sm" disabled={!onNext} onClick={onNext}>
                下一张
                <IconArrowRight aria-hidden="true" />
              </Button>
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={!ready || zoom <= 0.25}
            onClick={() => setZoom((value) => Math.max(0.25, value - 0.5))}
          >
            <IconZoomOut aria-hidden="true" />
            缩小
          </Button>
          <output aria-label="缩放比例" className="min-w-12 text-center text-sm tabular-nums">
            {ready ? `${Math.round(scale * 100)}%` : "—"}
          </output>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready || zoom >= Math.max(8, 2 / fit)}
            onClick={() => setZoom((value) => Math.min(Math.max(8, 2 / fit), value + 0.5))}
          >
            <IconZoomIn aria-hidden="true" />
            放大
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready}
            onClick={() => {
              setOriginalSize(true);
              setZoom(1);
            }}
          >
            原始尺寸
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready}
            onClick={() => {
              setZoom(1);
              setOriginalSize(false);
              setRotation(0);
              setFlipped(false);
            }}
          >
            适应窗口
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready}
            onClick={() => setRotation((value) => (value + 90) % 360)}
          >
            <IconRotateClockwise aria-hidden="true" />
            旋转
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready}
            aria-pressed={flipped}
            onClick={() => setFlipped((value) => !value)}
          >
            镜像
          </Button>
        </div>
        <div
          ref={setViewport}
          role="region"
          aria-label="图片查看区域"
          tabIndex={0}
          className="h-[65dvh] min-h-48 overflow-auto rounded-xl bg-muted/40 focus-visible:outline-2 focus-visible:outline-ring"
        >
          {imageError ? (
            <p role="alert" className="p-4 text-sm text-destructive">
              {imageError}
            </p>
          ) : (
            <>
              {(loading || (src && loaded !== src)) && (
                <p
                  role="status"
                  aria-label="图片加载状态"
                  className="p-4 text-sm text-muted-foreground"
                >
                  正在加载预览…
                </p>
              )}
              {!loading && !src && (
                <p className="p-4 text-sm text-muted-foreground">此项没有可用的预览图片。</p>
              )}
              {src && (
                <div className="grid min-h-full min-w-full w-max place-items-center p-4">
                  <div
                    className="relative shrink-0"
                    style={{ width: rotated ? height : width, height: rotated ? width : height }}
                  >
                    <img
                      key={src}
                      src={src}
                      alt={title}
                      className="absolute left-1/2 top-1/2 max-w-none"
                      style={{
                        width: width || undefined,
                        height: height || undefined,
                        visibility: ready ? "visible" : "hidden",
                        transform: `translate(-50%, -50%) rotate(${rotation}deg) scaleX(${flipped ? -1 : 1})`,
                      }}
                      onLoad={(event) => {
                        setNatural({
                          width: event.currentTarget.naturalWidth,
                          height: event.currentTarget.naturalHeight,
                        });
                        setLoaded(src);
                      }}
                      onError={() => setFailed(src)}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
