import React, { useState } from "react";
import {
  Select,
  Button,
  Modal,
  Card,
  Row,
  Col,
  Tag,
  Typography,
  Image,
} from "antd";
import {
  EyeOutlined,
  AppstoreOutlined,
  CheckCircleOutlined,
  PictureOutlined,
} from "@ant-design/icons";
import { useTheme } from "../../../shared/lib/useTheme";
import {
  KNOWN_TEMPLATES,
  getTemplateCdnUrl,
} from "../../../entities/report/model/templates";

const { Text, Paragraph } = Typography;

interface TemplateSelectorRendererProps {
  value: unknown;
  options?: unknown[];
  defaultValue?: unknown;
  onChange: (val: string) => void;
}

export const TemplateSelectorRenderer: React.FC<TemplateSelectorRendererProps> = ({
  value,
  options,
  defaultValue,
  onChange,
}) => {
  const { isDark } = useTheme();
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);

  const currentTemplate =
    typeof value === "string" && value
      ? value
      : typeof defaultValue === "string" && defaultValue
      ? defaultValue
      : "scrapbook";

  const templateOptions = Array.isArray(options) && options.length > 0
    ? options.map((opt) => String(opt))
    : KNOWN_TEMPLATES.map((t) => t.key);

  const currentMeta =
    KNOWN_TEMPLATES.find((t) => t.key === currentTemplate) || {
      key: currentTemplate,
      name: currentTemplate,
      desc: "自定义或外部模板",
      tag: "模板",
      tagColor: "blue",
    };

  const currentCdnUrl = getTemplateCdnUrl(currentTemplate);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
      {/* 顶部下拉选择与快捷按钮 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Select
          value={currentTemplate}
          onChange={(v) => onChange(v)}
          style={{ minWidth: 200, flex: 1 }}
          options={templateOptions.map((key) => {
            const info = KNOWN_TEMPLATES.find((t) => t.key === key);
            return {
              label: info ? `${info.name} [${info.tag}]` : key,
              value: key,
            };
          })}
        />
        <Button
          icon={<EyeOutlined />}
          onClick={() => setPreviewVisible(true)}
        >
          预览当前效果
        </Button>
        <Button
          type="primary"
          ghost
          icon={<AppstoreOutlined />}
          onClick={() => setGalleryOpen(true)}
        >
          浏览全部模板画廊
        </Button>
      </div>

      {/* 选定模板的实时缩略图与简介卡片 */}
      <div
        style={{
          display: "flex",
          gap: 14,
          padding: "10px 14px",
          borderRadius: 6,
          background: isDark ? "rgba(255, 255, 255, 0.03)" : "#f8fafc",
          border: `1px solid ${isDark ? "#303030" : "#e2e8f0"}`,
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: 72,
            height: 96,
            borderRadius: 4,
            overflow: "hidden",
            border: `1px solid ${isDark ? "#434343" : "#d9d9d9"}`,
            flexShrink: 0,
            cursor: "pointer",
            background: isDark ? "#000" : "#fff",
            position: "relative",
          }}
          onClick={() => setPreviewVisible(true)}
        >
          <Image
            src={currentCdnUrl}
            alt={currentTemplate}
            width={72}
            height={96}
            style={{ objectFit: "cover" }}
            preview={{
              visible: previewVisible,
              onVisibleChange: setPreviewVisible,
              src: currentCdnUrl,
            }}
            fallback="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='72' height='96' viewBox='0 0 72 96'><rect width='72' height='96' fill='%23333'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%23aaa' font-size='10'>预览图</text></svg>"
          />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Text strong style={{ fontSize: 13 }}>
              {currentMeta.name}
            </Text>
            <Tag color={currentMeta.tagColor} style={{ fontSize: 11 }}>
              {currentMeta.tag}
            </Tag>
          </div>
          <Paragraph
            type="secondary"
            style={{ margin: 0, fontSize: 12, lineHeight: "1.4" }}
          >
            {currentMeta.desc}
          </Paragraph>
          <Text
            type="secondary"
            style={{ fontSize: 11, display: "block", marginTop: 4 }}
          >
            💡 点击缩略图可全屏缩放预览完整长图，或点击上方「浏览全部模板画廊」进行对比选型。
          </Text>
        </div>
      </div>

      {/* 全部模板画廊弹窗 */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <PictureOutlined style={{ color: "#1677ff" }} />
            <span>报告模板视觉样式画廊</span>
          </div>
        }
        open={galleryOpen}
        onCancel={() => setGalleryOpen(false)}
        footer={null}
        width={960}
        styles={{ body: { maxHeight: "75vh", overflowY: "auto", padding: "16px 8px" } }}
      >
        <Image.PreviewGroup>
          <Row gutter={[16, 16]}>
            {KNOWN_TEMPLATES.map((tmpl) => {
              const isSelected = tmpl.key === currentTemplate;
              const cdnUrl = getTemplateCdnUrl(tmpl.key);

              return (
                <Col xs={24} sm={12} md={8} key={tmpl.key}>
                  <Card
                    hoverable
                    size="small"
                    style={{
                      borderColor: isSelected ? "#1677ff" : undefined,
                      borderWidth: isSelected ? 2 : 1,
                      background: isDark ? "#141414" : "#ffffff",
                    }}
                    styles={{
                      body: { padding: 12 },
                      cover: {
                        height: 180,
                        overflow: "hidden",
                        background: isDark ? "#000" : "#f5f5f5",
                        position: "relative",
                      },
                    }}
                    cover={
                      <Image
                        src={cdnUrl}
                        alt={tmpl.name}
                        style={{
                          width: "100%",
                          height: 180,
                          objectFit: "cover",
                          objectPosition: "top",
                        }}
                        fallback="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='180' viewBox='0 0 200 180'><rect width='200' height='180' fill='%23333'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%23aaa' font-size='12'>预览图</text></svg>"
                      />
                    }
                  >
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Text strong style={{ fontSize: 13 }}>
                          {tmpl.name}
                        </Text>
                        <Tag color={tmpl.tagColor} style={{ fontSize: 10, padding: "0 4px" }}>
                          {tmpl.tag}
                        </Tag>
                      </div>
                      <Text
                        type="secondary"
                        style={{ fontSize: 11, display: "block", marginTop: 4, minHeight: 32 }}
                      >
                        {tmpl.desc}
                      </Text>
                    </div>

                    <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end" }}>
                      {isSelected ? (
                        <Button
                          size="small"
                          type="dashed"
                          icon={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
                          disabled
                        >
                          当前使用中
                        </Button>
                      ) : (
                        <Button
                          size="small"
                          type="primary"
                          onClick={() => {
                            onChange(tmpl.key);
                            setGalleryOpen(false);
                          }}
                        >
                          应用此模板
                        </Button>
                      )}
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>
        </Image.PreviewGroup>
      </Modal>
    </div>
  );
};
