import { useState } from "react";
import { Button, Image, Spin, Typography, theme } from "antd";
import { PictureOutlined, ReloadOutlined, ZoomInOutlined } from "@ant-design/icons";
import type { ComicPromptTemplate } from "../model/useComicPromptEditor";
import { useComicTemplatePreview } from "../model/useComicTemplatePreview";

interface ComicTemplatePreviewProps {
  template?: ComicPromptTemplate;
  eager?: boolean;
  compact?: boolean;
  onOpen?: () => void;
}

/** 缩略图和画廊共用可重试、可放大的静态示例图。 */
export function ComicTemplatePreview({ template, eager, compact, onOpen }: ComicTemplatePreviewProps) {
  const preview = useComicTemplatePreview(template, eager, onOpen ? "thumbnail" : "full");
  const [zoomed, setZoomed] = useState(false);
  const { token } = theme.useToken();
  const emptyText = template ? "此模板暂无示例图" : "自定义提示词暂无示例图";
  return (
    <div
      ref={preview.targetRef}
      style={{
        minHeight: compact ? 96 : 200,
        height: compact ? 96 : onOpen ? 200 : undefined,
        width: "100%",
        display: "grid",
        placeItems: "center",
        background: token.colorFillQuaternary,
        borderRadius: token.borderRadius,
        overflow: "hidden",
      }}
      aria-busy={preview.status === "loading"}
    >
      {preview.status === "ready" && preview.src ? (
        onOpen ? (
          <button
            type="button"
            aria-label={`放大${template?.name}示例图`}
            onClick={onOpen}
            style={{ padding: 0, border: 0, width: "100%", height: "100%", background: "transparent", cursor: "zoom-in" }}
          >
            <img
              src={preview.src}
              alt={`${template?.name}漫画风格示例图`}
              onError={preview.imageFailed}
              style={{ display: "block", width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }}
            />
          </button>
        ) : (
          <div style={{ display: "grid", gap: 12, width: "100%", justifyItems: "center", paddingBottom: 12 }}>
            <Image
              src={preview.src}
              alt={`${template?.name}漫画风格示例图`}
              width="100%"
              onError={preview.imageFailed}
              preview={{ visible: zoomed, onVisibleChange: setZoomed }}
              style={{ maxHeight: 420, width: "100%", objectFit: "contain", display: "block" }}
            />
            <Button icon={<ZoomInOutlined />} onClick={() => setZoomed(true)}>放大查看完整图片</Button>
          </div>
        )
      ) : (
        <div style={{ display: "grid", justifyItems: "center", gap: 8, padding: compact ? 8 : 20, textAlign: "center" }}>
          {preview.status === "loading" ? <Spin size={compact ? "small" : "default"} /> : <PictureOutlined style={{ fontSize: compact ? 18 : 28, color: token.colorTextQuaternary }} />}
          {!compact && preview.status === "loading" && <Typography.Text type="secondary">正在加载示例图</Typography.Text>}
          {preview.status === "empty" && <Typography.Text type="secondary" style={{ fontSize: compact ? 11 : 13 }}>{compact ? "暂无示例图" : emptyText}</Typography.Text>}
          {preview.status === "error" && (
            <>
              <Typography.Text type="danger" role="alert" title={preview.error}>{compact ? "加载失败" : preview.error}</Typography.Text>
              <Button size="small" icon={<ReloadOutlined />} onClick={preview.retry}>重试</Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
