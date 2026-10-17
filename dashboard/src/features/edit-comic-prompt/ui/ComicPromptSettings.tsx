import { useState } from "react";
import { Alert, Button, Input, Modal, Popconfirm, Select, Space, Typography, theme } from "antd";
import { AppstoreOutlined, CopyOutlined, EyeOutlined } from "@ant-design/icons";
import { comicPromptTemplates, useComicPromptEditor } from "../model/useComicPromptEditor";
import { ComicTemplatePreview } from "./ComicTemplatePreview";
import { ComicTemplateGallery } from "./ComicTemplateGallery";

interface ComicPromptSettingsProps {
  value: unknown;
  onChange: (value: unknown) => void;
  idPrefix: string;
}

/** 漫画全局风格选择、内置预览及自定义编辑。 */
export function ComicPromptSettings({ value, onChange, idPrefix }: ComicPromptSettingsProps) {
  const { token } = theme.useToken();
  const editor = useComicPromptEditor(value, onChange);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const previewTemplate = comicPromptTemplates.find(({ id }) => id === previewId);
  return (
    <div style={{ display: "grid", gap: 14, minWidth: 0 }}>
      <div style={{ display: "grid", gap: 6 }}>
        <label htmlFor={`${idPrefix}-template`}>默认漫画提示词模板</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <Select
            id={`${idPrefix}-template`}
            value={editor.selection}
            onChange={(id: string) => { editor.selectTemplate(id); setPreviewId(null); }}
            style={{ minWidth: 180, flex: "1 1 220px", maxWidth: "100%" }}
            showSearch
            virtual={false}
            optionFilterProp="label"
            options={[
              ...comicPromptTemplates.map(({ id, name }) => ({ value: id, label: name })),
              { value: "custom", label: "自定义" },
            ]}
          />
          <Button icon={<EyeOutlined />} onClick={() => setPreviewId(editor.selection)}>
            预览当前效果
          </Button>
          <Button type="primary" ghost icon={<AppstoreOutlined />} onClick={() => setGalleryOpen(true)}>
            浏览全部模板画廊
          </Button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", padding: 12, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: token.borderRadiusLG, background: token.colorFillQuaternary }}>
        <div style={{ width: 80, flexShrink: 0 }}>
          <ComicTemplatePreview template={editor.preset} eager compact onOpen={() => setPreviewId(editor.selection)} />
        </div>
        <div style={{ minWidth: 0 }}>
          <Typography.Text strong>{editor.preset?.name ?? "自定义漫画提示词"}</Typography.Text>
          <Typography.Paragraph type="secondary" style={{ margin: "6px 0", lineHeight: 1.6 }}>
            {editor.preset?.description ?? "使用自己的场景分析提示词；切换内置风格会保留这里的自定义文本。"}
          </Typography.Paragraph>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {editor.preset?.preview ? "点击缩略图可放大查看。示例图仅供风格参考，实际画面由群聊内容与绘图模型决定。" : "当前选项暂无静态示例图，可在画廊中对比其他风格。"}
          </Typography.Text>
        </div>
      </div>
      {editor.preset ? (
        <>
          <Space wrap>
            <Popconfirm
              title="替换自定义提示词？"
              description="将当前内置模板复制到自定义编辑区，替换原有自定义内容。"
              disabled={!editor.custom.trim() || editor.custom === editor.preset.prompt}
              onConfirm={editor.copyPreset}
              okText="复制并替换"
              cancelText="保留原文"
            >
              <Button
                icon={<CopyOutlined />}
                onClick={() => {
                  if (!editor.custom.trim() || editor.custom === editor.preset?.prompt) editor.copyPreset();
                }}
              >
                复制为自定义
              </Button>
            </Popconfirm>
            <Typography.Text type="secondary">切换风格会保留自定义文本。</Typography.Text>
          </Space>
          <details>
            <summary style={{ cursor: "pointer", padding: "8px 0", color: token.colorPrimary }}>
              查看完整内置提示词
            </summary>
            <Input.TextArea
              aria-label={`${editor.preset.name}提示词预览`}
              value={editor.preset.prompt}
              readOnly
              autoSize={{ minRows: 8, maxRows: 16 }}
              style={{ marginTop: 8, lineHeight: 1.7 }}
            />
          </details>
        </>
      ) : (
        <div style={{ display: "grid", gap: 6 }}>
          <label htmlFor={`${idPrefix}-custom`}>自定义漫画场景分析提示词</label>
          <Input.TextArea
            id={`${idPrefix}-custom`}
            value={editor.custom}
            onChange={(event) => editor.editCustom(event.target.value)}
            autoSize={{ minRows: 10, maxRows: 22 }}
            placeholder="留空使用原版漫画提示词"
            aria-describedby={`${idPrefix}-hint`}
            style={{ lineHeight: 1.7 }}
          />
          <Typography.Text id={`${idPrefix}-hint`} type="secondary">
            {"保留 ${topic_count} 和 ${chat_content}，输出需包含完整的 scene 字符串。留空时使用原版漫画。"}
          </Typography.Text>
        </div>
      )}
      <Typography.Text type="secondary">
        角色方案中的专属提示词优先。要跟随这里的风格，请将角色的「漫画场景分析提示词」留空。
      </Typography.Text>
      <ComicTemplateGallery
        open={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        selectedIds={[editor.selection]}
        onPreview={setPreviewId}
        onSelect={(id) => { editor.selectTemplate(id); setGalleryOpen(false); setPreviewId(null); }}
      />
      <Modal
        title={`${previewTemplate?.name ?? "自定义提示词"} · 风格示例`}
        open={previewId !== null}
        onCancel={() => setPreviewId(null)}
        footer={null}
        width={900}
        destroyOnHidden
      >
        {previewId !== null && <ComicTemplatePreview key={previewId} template={previewTemplate} eager />}
        <Alert style={{ marginTop: 12 }} type="info" showIcon message="静态示例图仅供风格参考，实际生成效果取决于群聊内容、角色参考图及绘图模型。" />
      </Modal>
    </div>
  );
}
