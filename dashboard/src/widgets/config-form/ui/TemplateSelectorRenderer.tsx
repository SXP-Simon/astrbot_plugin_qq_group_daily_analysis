import React, { useEffect, useMemo, useState } from "react";
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
  DownloadOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useTheme } from "../../../shared/lib/useTheme";
import {
  KNOWN_TEMPLATES,
  getTemplateCdnUrl,
  ReportTemplateItem,
} from "../../../entities/report/model/templates";
import { fetchReportTemplates, fetchTemplatePreview } from "../../../entities/report/api/reportApi";
import { TemplateInstallModal } from "../../../features/install-template/ui/TemplateInstallModal";
import { TemplateUninstallModal } from "../../../features/install-template/ui/TemplateUninstallModal";

const GALLERY_FALLBACK =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='180' viewBox='0 0 200 180'><rect width='200' height='180' fill='%23333'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%23aaa' font-size='12'>预览图</text></svg>";

/** 自定义模板的预览图：按需从后端取模板目录内 preview.jpg 等 */
const CustomPreviewImage: React.FC<{ templateName: string; height?: number }> = ({
  templateName,
  height = 180,
}) => {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSrc(null);
    fetchTemplatePreview(templateName).then((url) => {
      if (!cancelled && url) setSrc(url);
    });
    return () => {
      cancelled = true;
    };
  }, [templateName]);

  return (
    <Image
      src={src || GALLERY_FALLBACK}
      alt={templateName}
      style={{ width: "100%", height, objectFit: "cover", objectPosition: "top" }}
      fallback={GALLERY_FALLBACK}
      preview={{ src: src || undefined }}
    />
  );
};

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
  const [installOpen, setInstallOpen] = useState(false);
  const [uninstallOpen, setUninstallOpen] = useState(false);
  const [remoteTemplates, setRemoteTemplates] = useState<ReportTemplateItem[]>([]);

  useEffect(() => {
    // 拉取全量模板（含自定义模板的 display_name/desc/tag 元信息，失败则静默降级）
    fetchReportTemplates()
      .then((list) => setRemoteTemplates(Array.isArray(list) ? list : []))
      .catch(() => setRemoteTemplates([]));
  }, []);

  const currentTemplate =
    typeof value === "string" && value
      ? value
      : typeof defaultValue === "string" && defaultValue
      ? defaultValue
      : "scrapbook";

  // 下拉选项：schema options（内置）为基底，追加 API 返回的自定义模板；
  // 展示名为 API 元信息（display_name/tag/desc）优先，KNOWN_TEMPLATES 兜底
  const templateOptions = useMemo(() => {
    const baseKeys =
      Array.isArray(options) && options.length > 0
        ? options.map((opt) => String(opt))
        : KNOWN_TEMPLATES.map((t) => t.key);
    const remoteCustom = (remoteTemplates || []).filter(
      (t) => t.is_custom === true && !baseKeys.includes(t.id)
    );
    return [...baseKeys, ...remoteCustom.map((t) => t.id)].map((key) => {
      const remote = (remoteTemplates || []).find((t) => t.id === key);
      const known = KNOWN_TEMPLATES.find((t) => t.key === key);
      const displayName = remote?.display_name || known?.name || key;
      const tag = remote?.tag || known?.tag || "";
      return {
        label: tag ? `${displayName} [${tag}]` : displayName,
        value: key,
        title: remote?.desc || known?.desc || "",
      };
    });
  }, [options, remoteTemplates]);

  // 画廊条目：API 全量（内置+自定义）为基底，并集 KNOWN_TEMPLATES（覆盖 format 等
  // 未被 API 列出的内置模板），元信息 API 优先、KNOWN 兜底
  const galleryItems = useMemo(() => {
    const items: ReportTemplateItem[] = [...remoteTemplates];
    KNOWN_TEMPLATES.forEach((k) => {
      if (!items.some((t) => t.id === k.key)) {
        items.push({ id: k.key, is_custom: false } as ReportTemplateItem);
      }
    });
    return items.map((remote) => {
      const known = KNOWN_TEMPLATES.find((t) => t.key === remote.id);
      return {
        key: remote.id,
        isCustom: Boolean(remote.is_custom),
        name: remote.display_name || known?.name || remote.id,
        desc: remote.desc || known?.desc || "",
        tag: remote.tag || known?.tag || "",
        tagColor: remote.tag_color || known?.tagColor || "default",
      };
    });
  }, [remoteTemplates]);

  // 当前选中模板的展示信息：与画廊/下拉同源的元信息合并（API 优先、KNOWN 兜底）
  const currentMeta =
    galleryItems.find((g) => g.key === currentTemplate) || {
      key: currentTemplate,
      isCustom: false,
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
          options={templateOptions}
          optionFilterProp="label"
          showSearch
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
        <Button
          icon={<DownloadOutlined />}
          onClick={() => setInstallOpen(true)}
        >
          安装模板
        </Button>
        <Button
          icon={<DeleteOutlined />}
          onClick={() => setUninstallOpen(true)}
        >
          卸载模板
        </Button>
      </div>
      <TemplateInstallModal
        open={installOpen}
        onClose={() => setInstallOpen(false)}
      />
      <TemplateUninstallModal
        open={uninstallOpen}
        onClose={() => setUninstallOpen(false)}
      />

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
          {currentMeta.isCustom ? (
            <CustomPreviewImage templateName={currentTemplate} height={96} />
          ) : (
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
          )}
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
            {galleryItems.map((tmpl) => {
              const isSelected = tmpl.key === currentTemplate;
              const isCustom = tmpl.isCustom;

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
                      isCustom ? (
                        <CustomPreviewImage templateName={tmpl.key} />
                      ) : (
                        <Image
                          src={getTemplateCdnUrl(tmpl.key)}
                          alt={tmpl.name}
                          style={{
                            width: "100%",
                            height: 180,
                            objectFit: "cover",
                            objectPosition: "top",
                          }}
                          fallback={GALLERY_FALLBACK}
                        />
                      )
                    }
                  >
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Text strong style={{ fontSize: 13 }}>
                          {tmpl.name}
                          {isCustom && (
                            <Tag color="blue" style={{ fontSize: 10, marginLeft: 6, padding: "0 4px" }}>
                              自定义
                            </Tag>
                          )}
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
