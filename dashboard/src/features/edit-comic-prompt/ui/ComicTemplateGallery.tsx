import { Button, Card, Col, Modal, Row, Tag, Typography, theme } from "antd";
import { CheckCircleOutlined } from "@ant-design/icons";
import { comicPromptTemplates } from "../model/useComicPromptEditor";
import { ComicTemplatePreview } from "./ComicTemplatePreview";

interface ComicTemplateGalleryProps {
  open: boolean;
  onClose: () => void;
  onPreview: (id: string) => void;
  selectedIds: string[];
  onSelect: (id: string) => void;
  multiple?: boolean;
  disabled?: boolean;
}

/** 固定模板与自动切换候选共用同一份示例图画廊。 */
export function ComicTemplateGallery({ open, onClose, onPreview, selectedIds, onSelect, multiple = false, disabled = false }: ComicTemplateGalleryProps) {
  const { token } = theme.useToken();
  return <Modal
    title="漫画模板视觉样式画廊"
    open={open}
    onCancel={onClose}
    footer={null}
    width={1040}
    destroyOnHidden
    styles={{ body: { maxHeight: "72vh", overflowY: "auto", padding: "12px 8px" } }}
  >
    <Typography.Paragraph type="secondary">
      {multiple ? "点击图片可放大查看；添加的模板会排在候选末尾，保存配置后生效。" : "这些是预先制作的风格示例，并非当前群聊的生成结果。点击图片可放大查看，选用模板后保存配置生效。"}
    </Typography.Paragraph>
    <Row gutter={[16, 16]}>
      {comicPromptTemplates.map((template) => {
        const selected = selectedIds.includes(template.id);
        const selectedLabel = multiple ? "已加入候选" : "当前使用中";
        return <Col xs={24} sm={12} lg={8} key={template.id} style={{ display: "flex" }}>
          <Card size="small" style={{ width: "100%", borderColor: selected ? token.colorPrimary : token.colorBorderSecondary, boxShadow: selected ? `inset 0 0 0 1px ${token.colorPrimary}` : undefined }} styles={{ body: { display: "grid", gap: 10, height: "100%", alignContent: "start" } }}>
            <ComicTemplatePreview template={template} onOpen={() => onPreview(template.id)} />
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
              <Typography.Text strong>{template.name}</Typography.Text>
              {selected && <Tag color="blue" icon={<CheckCircleOutlined />}>{selectedLabel}</Tag>}
            </div>
            <Typography.Paragraph type="secondary" style={{ margin: 0, minHeight: 44, fontSize: 12 }}>{template.description}</Typography.Paragraph>
            <Button type={selected ? "default" : "primary"} disabled={selected || disabled} aria-label={selected ? `${template.name}${selectedLabel}` : `${multiple ? "添加候选" : "选用"}${template.name}`} onClick={() => onSelect(template.id)}>
              {selected ? selectedLabel : multiple ? "添加到候选末尾" : "应用此模板"}
            </Button>
          </Card>
        </Col>;
      })}
    </Row>
  </Modal>;
}
