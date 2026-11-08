import { LoadingState } from "./loading-state";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
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
  fitMode?: "contain" | "width";
  loading?: boolean;
  error?: string;
  position?: string;
  onPrevious?: () => void;
  onNext?: () => void;
  onClose: () => void;
}

/** 可嵌入报告或文件弹窗的图片查看区域，共用缩放与手势行为。 */
export function ImageViewer({
  src,
  title,
  loading,
  error,
  position,
  onPrevious,
  onNext,
  fitMode = "contain",
}: Omit<ImagePreviewProps, "onClose">) {
  const frame = useRef<HTMLDivElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const anchor = useRef<{ x: number; y: number; relativeX: number; relativeY: number } | null>(
    null,
  );
  const [dragging, setDragging] = useState(false);
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
    pointers.current.clear();
    setDragging(false);
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
          fitMode === "width" ? 1 : Math.max(1, bounds.height - 32) / natural.height,
        )
      : 1;
  const scale = (originalSize ? 1 : fit) * zoom;
  const width = natural.width * scale;
  const height = natural.height * scale;
  const rotated = rotation % 180 !== 0;

  // 图片尺寸更新后还原鼠标或双指中心的位置，避免放大时跳到左上角。
  useLayoutEffect(() => {
    const point = anchor.current;
    if (!point || !viewport || !frame.current) return;
    const rect = frame.current.getBoundingClientRect();
    viewport.scrollLeft += rect.left + point.relativeX * rect.width - point.x;
    viewport.scrollTop += rect.top + point.relativeY * rect.height - point.y;
    anchor.current = null;
  }, [width, height, viewport, rotation]);
  const changeZoom = (next: number, x?: number, y?: number) => {
    if (!ready || !viewport || !frame.current) return;
    const nextZoom = Math.max(0.25, Math.min(Math.max(8, 2 / fit), next));
    if (nextZoom === zoom) return;
    const area = viewport.getBoundingClientRect();
    const rect = frame.current.getBoundingClientRect();
    const clientX = x ?? area.left + area.width / 2;
    const clientY = y ?? area.top + area.height / 2;
    anchor.current = {
      x: clientX,
      y: clientY,
      relativeX: rect.width ? (clientX - rect.left) / rect.width : 0.5,
      relativeY: rect.height ? (clientY - rect.top) / rect.height : 0.5,
    };
    setZoom(nextZoom);
  };
  useEffect(() => {
    if (!viewport || !ready) return;
    const wheel = (event: WheelEvent) => {
      // 必须使用非被动监听，避免缩放图片时同时滚动弹窗或缩放整个页面。
      event.preventDefault();
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY) && !event.ctrlKey) {
        viewport.scrollLeft += event.deltaX;
        return;
      }
      const delta =
        event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? bounds.height : 1);
      changeZoom(
        zoom * Math.exp(-Math.max(-100, Math.min(100, delta)) * 0.005),
        event.clientX,
        event.clientY,
      );
    };
    viewport.addEventListener("wheel", wheel, { passive: false });
    return () => viewport.removeEventListener("wheel", wheel);
  });

  return (
    <>
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
          onClick={() => changeZoom(zoom / 1.5)}
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
          onClick={() => changeZoom(zoom * 1.5)}
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
          {fitMode === "width" ? "适应宽度" : "适应窗口"}
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
      <p className="m-0 text-xs text-muted-foreground">滚轮缩放，拖动查看；触屏可双指缩放。</p>
      <div
        ref={setViewport}
        role="region"
        aria-label="图片查看区域"
        tabIndex={0}
        aria-busy={Boolean(loading || (src && loaded !== src && !imageError))}
        className="h-[65dvh] min-h-48 overflow-auto overscroll-contain rounded-xl bg-muted/40 focus-visible:outline-2 focus-visible:outline-ring"
        style={{
          touchAction: ready ? "none" : "auto",
          cursor: ready ? (dragging ? "grabbing" : "grab") : undefined,
        }}
        onPointerDown={(event) => {
          if (!ready || event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
          setDragging(true);
        }}
        onPointerMove={(event) => {
          const previous = pointers.current.get(event.pointerId);
          if (!previous) return;
          const other = [...pointers.current].find(([id]) => id !== event.pointerId)?.[1];
          pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
          if (other) {
            const oldDistance = Math.hypot(previous.x - other.x, previous.y - other.y);
            const distance = Math.hypot(event.clientX - other.x, event.clientY - other.y);
            if (oldDistance > 0)
              changeZoom(
                (zoom * distance) / oldDistance,
                (event.clientX + other.x) / 2,
                (event.clientY + other.y) / 2,
              );
          }
          event.currentTarget.scrollLeft -= (event.clientX - previous.x) / (other ? 2 : 1);
          event.currentTarget.scrollTop -= (event.clientY - previous.y) / (other ? 2 : 1);
        }}
        onPointerUp={(event) => {
          pointers.current.delete(event.pointerId);
          setDragging(pointers.current.size > 0);
        }}
        onPointerCancel={(event) => {
          pointers.current.delete(event.pointerId);
          setDragging(pointers.current.size > 0);
        }}
        onLostPointerCapture={(event) => {
          pointers.current.delete(event.pointerId);
          setDragging(pointers.current.size > 0);
        }}
        onDoubleClick={() => {
          setOriginalSize(!originalSize);
          setZoom(1);
        }}
        onKeyDown={(event) => {
          if (event.key === "+" || event.key === "=") {
            event.preventDefault();
            changeZoom(zoom * 1.5);
          }
          if (event.key === "-") {
            event.preventDefault();
            changeZoom(zoom / 1.5);
          }
          if (event.key === "0") {
            event.preventDefault();
            setOriginalSize(false);
            setZoom(1);
          }
        }}
      >
        {imageError ? (
          <p role="alert" className="p-4 text-sm text-destructive">
            {imageError}
          </p>
        ) : (
          <>
            {(loading || (src && loaded !== src)) && (
              <LoadingState
                key={title}
                slowAfterMs={30_000}
                aria-label="图片加载状态"
                className="p-4 text-sm text-muted-foreground"
              >
                正在加载预览…
              </LoadingState>
            )}
            {!loading && !src && (
              <p className="p-4 text-sm text-muted-foreground">此项没有可用的预览图片。</p>
            )}
            {src && (
              <div className="grid min-h-full min-w-full w-max place-items-center p-4">
                <div
                  ref={frame}
                  className="relative shrink-0"
                  style={{ width: rotated ? height : width, height: rotated ? width : height }}
                >
                  <img
                    key={src}
                    src={src}
                    draggable={false}
                    alt={title}
                    className="absolute left-1/2 top-1/2 max-w-none select-none"
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
    </>
  );
}

/** 弹窗入口沿用同一查看器，避免各处分别维护图片操作。 */
export function ImagePreview({ title, onClose, ...props }: ImagePreviewProps) {
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
        <ImageViewer {...props} title={title} />
      </DialogContent>
    </Dialog>
  );
}
