import React, { useState, useEffect } from "react";
import {
  Card,
  Row,
  Col,
  Input,
  Typography,
  Space,
  Button,
  Tag,
  Empty,
  Badge,
  Spin,
  Alert,
  Drawer,
  Modal,
  Popconfirm,
} from "antd";
import {
  SaveOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  AppstoreOutlined,
  DownOutlined,
  UpOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import { useConfigViewModel } from "../model/useConfigViewModel";
import { FieldRenderer } from "../../../widgets/config-form/ui/FieldRenderer";
import { useTheme } from "../../../shared/lib/useTheme";
import { MarkdownHint } from "../../../shared/ui/MarkdownHint";
import { WordCloudEditor } from "../../../features/edit-wordcloud/ui/WordCloudEditor";
import { WordCloudSettings } from "./WordCloudSettings";
import { ComicTemplateRotationSettings } from "../../../features/edit-comic-prompt/ui/ComicTemplateRotationSettings";
import { COMIC_ROTATION_FIELDS } from "../../../features/edit-comic-prompt/model/comicTemplateRotation";

const { Title, Text, Paragraph } = Typography;

interface ConfigPageProps {
  viewModel: ReturnType<typeof useConfigViewModel>;
}

export const ConfigPage: React.FC<ConfigPageProps> = ({ viewModel }) => {
  const { isDark } = useTheme();
  const [isMobileScreen, setIsMobileScreen] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [wordCloudEditorOpen, setWordCloudEditorOpen] = useState(false);
  const [wordCloudCatalogRevision, setWordCloudCatalogRevision] = useState(0);
  const [wordCloudScope, setWordCloudScope] = useState<string | undefined>();

  useEffect(() => {
    const handleResize = () => {
      setIsMobileScreen(window.innerWidth < 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const {
    templateCdnBaseUrl,
    loading,
    configLoaded,
    saving,
    isDirty,
    categories,
    providers,
    personas,
    activeCategory,
    currentGroupFields,
    activeGroupMeta,
    searchQuery,
    errors,
    groupErrorCounts,
    setSearchQuery,
    setActiveCategory,
    handleFieldChange,
    handleSave,
    handleReload,
    formData,
    wordCloudDirty,
    comicDirty,
    savedDailyComic,
    reloadConfirmationOpen,
    cancelReload,
    confirmReload,
    handleGroupPatch,
    restoreSavedWordCloud,
  } = viewModel;

  const activeCategoryInfo = categories.find((c) => c.key === activeCategory);
  const wordCloudValue = formData.wordcloud ?? {};
  const groupOverrides = wordCloudValue.group_overrides;
  const overridesObject: Record<string, unknown> = groupOverrides && typeof groupOverrides === "object" && !Array.isArray(groupOverrides) ? groupOverrides as Record<string, unknown> : {};
  const scopedOverride = wordCloudScope ? overridesObject[wordCloudScope] : undefined;
  const scopedObject: Record<string, unknown> = scopedOverride && typeof scopedOverride === "object" && !Array.isArray(scopedOverride) ? scopedOverride as Record<string, unknown> : {};
  const editorValue = wordCloudScope ? { ...wordCloudValue, ...scopedObject } : wordCloudValue;
  const patchEditor = (patch: Record<string, unknown>) => {
    if (wordCloudScope) {
      const nextOverride = { ...scopedObject };
      for (const [key, next] of Object.entries(patch)) {
        if (next === undefined) delete nextOverride[key];
        else nextOverride[key] = next;
      }
      const nextOverrides = { ...overridesObject };
      if (Object.keys(nextOverride).length) nextOverrides[wordCloudScope] = nextOverride;
      else delete nextOverrides[wordCloudScope];
      handleGroupPatch("wordcloud", { group_overrides: nextOverrides });
    } else handleGroupPatch("wordcloud", patch);
  };
  const protectedFonts = [wordCloudValue.font, ...(groupOverrides && typeof groupOverrides === "object" && !Array.isArray(groupOverrides) ? Object.values(groupOverrides).map((entry: unknown) => entry && typeof entry === "object" && "font" in entry ? entry.font : undefined) : [])].filter((font): font is string => typeof font === "string");
  const comicPrompts = formData.prompts?.comic_analysis_prompts;
  const comicCustomPrompt = comicPrompts && typeof comicPrompts === "object" && "comic_storyboard_prompt" in comicPrompts ? comicPrompts.comic_storyboard_prompt : undefined;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: "100%",
        position: "relative",
      }}
    >
      {/* 顶部概览与全局操作栏 (Sticky 吸顶固定，确保在长表单滚动中常驻可视且可一键保存) */}
      <Card
        size="small"
        style={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          background: isDark ? "#141414" : "#ffffff",
          borderRadius: 6,
          boxShadow: isDark
            ? "0 4px 12px rgba(0, 0, 0, 0.45)"
            : "0 4px 12px rgba(0, 0, 0, 0.06)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <SettingOutlined style={{ color: "#1677ff", fontSize: 18 }} />
              <Title level={4} style={{ margin: 0, fontSize: 16 }}>
                群聊分析配置中心
              </Title>
              {isDirty && (
                <Tag color="warning" icon={<ExclamationCircleOutlined />}>
                  存在未保存的修改
                </Tag>
              )}
            </div>
            <Paragraph
              type="secondary"
              style={{ margin: "4px 0 0 0", fontSize: 12 }}
            >
              基于最新版 <code>_conf_schema.json</code> 动态生成，升级新增字段会自动显示。修改后请点击右上角保存。
            </Paragraph>
          </div>

          <Space size="small" wrap>
            <Tag color="blue" style={{ fontSize: 12, padding: "2px 8px" }}>
              {categories.length} 个配置分组
            </Tag>
            <Button
              size="middle"
              icon={<ReloadOutlined spin={loading} />}
              onClick={handleReload}
              disabled={loading || saving}
            >
              重新读取
            </Button>
            <Button
              size="middle"
              type="primary"
              icon={isDirty ? <SaveOutlined /> : <CheckCircleOutlined />}
              onClick={handleSave}
              loading={saving}
              disabled={!isDirty || loading || !configLoaded}
            >
              {isDirty ? "保存配置" : "配置已同步"}
            </Button>
          </Space>
        </div>
      </Card>

      {/* 主体配置工作区 (双栏布局：左侧分组导航 + 右侧动态表单) */}
      <Card size="small" styles={{ body: { padding: 0 } }}>
        <Spin spinning={loading}>
          <Row style={{ minHeight: 600 }}>
            {/* 左侧：搜索与分组导航 (桌面端 Sticky 固定，移动端支持一键收纳展开) */}
            <Col
              xs={24}
              md={6}
              style={{
                borderRight: !isMobileScreen ? `1px solid ${isDark ? "#303030" : "#f0f0f0"}` : undefined,
                borderBottom: isMobileScreen ? `1px solid ${isDark ? "#303030" : "#f0f0f0"}` : undefined,
                padding: isMobileScreen ? "12px 16px" : "16px 12px",
                background: isDark ? "#141414" : "#fafafa",
                position: isMobileScreen ? "static" : "sticky",
                top: 72,
                maxHeight: isMobileScreen ? undefined : "calc(100vh - 88px)",
                overflowY: isMobileScreen ? undefined : "auto",
                alignSelf: "flex-start",
                zIndex: 10,
              }}
            >
              {/* 移动端分组切换与收纳指示栏 */}
              {isMobileScreen && (
                <div
                  onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: isDark ? "#1f1f1f" : "#f0f2f5",
                    cursor: "pointer",
                    marginBottom: mobileMenuOpen ? 12 : 0,
                    border: `1px solid ${isDark ? "#303030" : "#e4e7eb"}`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
                    <AppstoreOutlined style={{ color: "#1677ff", fontSize: 16, flexShrink: 0 }} />
                    <span style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      当前分组: {activeCategoryInfo?.label || activeCategory}
                    </span>
                    {activeCategoryInfo && (
                      <Tag color="blue" style={{ margin: 0, fontSize: 11, padding: "0 6px" }}>
                        {activeCategoryInfo.totalFields} 项
                      </Tag>
                    )}
                    {(groupErrorCounts[activeCategory] || 0) > 0 && (
                      <Badge count={groupErrorCounts[activeCategory]} />
                    )}
                  </div>
                  <Button
                    size="small"
                    type="link"
                    icon={mobileMenuOpen ? <UpOutlined /> : <DownOutlined />}
                    style={{ padding: 0, fontSize: 12, flexShrink: 0 }}
                  >
                    {mobileMenuOpen ? "收起分组" : "切换分组"}
                  </Button>
                </div>
              )}

              {/* 搜索框与分组列表 (桌面端常驻，移动端点击展开后显示) */}
              {(!isMobileScreen || mobileMenuOpen) && (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Input
                      placeholder="搜索配置名称或说明"
                      prefix={<SearchOutlined style={{ color: "#8c8c8c" }} />}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      allowClear
                    />
                  </div>

                  {/* 分组列表 */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {categories.map((cat) => {
                      const isActive = activeCategory === cat.key;
                      const isVisible =
                        cat.matchCount === undefined || cat.matchCount > 0;
                      const errCount = groupErrorCounts[cat.key] || 0;

                      if (!isVisible) return null;

                      return (
                        <div
                          key={cat.key}
                          onClick={() => {
                            setActiveCategory(cat.key);
                            if (isMobileScreen) {
                              setMobileMenuOpen(false);
                            }
                          }}
                          style={{
                            padding: "9px 12px",
                            borderRadius: 6,
                            cursor: "pointer",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            fontSize: 13,
                            fontWeight: isActive ? 600 : 400,
                            background: isActive
                              ? "#1677ff"
                              : isDark
                                ? "transparent"
                                : "transparent",
                            color: isActive
                              ? "#ffffff"
                              : isDark
                                ? "#d9d9d9"
                                : "#262626",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {cat.label}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {errCount > 0 && (
                              <Badge
                                count={errCount}
                                title={`${errCount} 项填写有误`}
                                style={{
                                  backgroundColor: "#ff4d4f",
                                  boxShadow: "none",
                                }}
                              />
                            )}
                            {cat.matchCount !== undefined ? (
                              <Badge
                                count={cat.matchCount}
                                style={{
                                  backgroundColor: isActive ? "#ffffff" : "#1677ff",
                                  color: isActive ? "#1677ff" : "#ffffff",
                                }}
                              />
                            ) : errCount === 0 ? (
                              <Text
                                style={{
                                  fontSize: 11,
                                  color: isActive ? "rgba(255, 255, 255, 0.75)" : "#8c8c8c",
                                }}
                              >
                                {cat.totalFields} 项
                              </Text>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </Col>

            {/* 右侧：分组详情与表单项 */}
            <Col xs={24} md={18} style={{ padding: isMobileScreen ? "16px 12px" : "20px 24px", minWidth: 0 }}>
              {activeGroupMeta && (
                <div
                  style={{
                    marginBottom: 20,
                    paddingBottom: 12,
                    borderBottom: `1px solid ${isDark ? "#282828" : "#f0f0f0"}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-end",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <div style={{ flex: 1, marginRight: 12 }}>
                    <Title level={4} style={{ margin: 0, fontSize: 16 }}>
                      {activeGroupMeta.description || activeCategory}
                    </Title>
                    {activeGroupMeta.hint && (
                      <MarkdownHint
                        content={activeGroupMeta.hint}
                        style={{
                          fontSize: 12,
                          display: "block",
                          marginTop: 4,
                          color: isDark ? "#8c8c8c" : "#595959",
                          lineHeight: 1.6,
                        }}
                      />
                    )}
                  </div>
                  <Tag color="default" style={{ margin: 0 }}>
                    字段数: {currentGroupFields.length}
                  </Tag>
                </div>
              )}

              {groupErrorCounts[activeCategory] > 0 && (
                <Alert
                  type="error"
                  showIcon
                  message={`当前分组内有 ${groupErrorCounts[activeCategory]} 项配置填写有误，请核对并修改标红字段。`}
                  style={{ marginBottom: 16, borderRadius: 6 }}
                />
              )}

              {currentGroupFields.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    searchQuery
                      ? "未找到匹配该关键词的配置项"
                      : "该分组下暂无可配置字段"
                  }
                  style={{ margin: "60px 0" }}
                />
              ) : activeCategory === "wordcloud" ? (
                <WordCloudSettings fields={currentGroupFields} value={formData.wordcloud} errors={errors.wordcloud} disabled={!configLoaded || saving} editorOpen={wordCloudEditorOpen} catalogRevision={wordCloudCatalogRevision} searching={!!searchQuery.trim()} dirty={wordCloudDirty} onRestoreSaved={restoreSavedWordCloud} onEditGroupAppearance={(umo) => { setWordCloudScope(umo); setWordCloudEditorOpen(true); }} onChange={(key, value) => handleFieldChange("wordcloud", key, value)} onOpenEditor={() => { setWordCloudScope(undefined); setWordCloudEditorOpen(true); }} />
              ) : (
                <Row gutter={[16, 0]}>
                  {activeCategory === "daily_comic" && (!searchQuery.trim() || currentGroupFields.some(({ key }) => COMIC_ROTATION_FIELDS.includes(key))) && <Col span={24}>
                    <ComicTemplateRotationSettings
                      value={formData.daily_comic ?? {}}
                      savedValue={savedDailyComic}
                      dirty={comicDirty}
                      disabled={!configLoaded || saving}
                      customPrompt={comicCustomPrompt}
                      errors={errors.daily_comic}
                      onPatch={(patch) => handleGroupPatch("daily_comic", patch)}
                      onOpenPromptSettings={() => { setSearchQuery(""); setActiveCategory("prompts"); requestAnimationFrame(() => document.getElementById("cfg-field-prompts-comic_analysis_prompts")?.scrollIntoView({ block: "center" })); }}
                    />
                  </Col>}
                  {currentGroupFields.filter(({ key }) => activeCategory !== "daily_comic" || !COMIC_ROTATION_FIELDS.includes(key)).map((field) => {
                    const isLongField =
                      field.schema.type === "template_list" ||
                      field.schema.type === "object" ||
                      field.schema.type === "list" ||
                      field.schema.type === "text" ||
                      field.schema.type === "file" ||
                      field.key.includes("prompt") ||
                      field.key.includes("template") ||
                      field.key.toLowerCase().includes("provider") ||
                      field.key.toLowerCase().includes("persona") ||
                      field.schema._special === "select_persona" ||
                      field.schema._special === "select_provider" ||
                      (field.schema.description && field.schema.description.length > 25) ||
                      (field.schema.hint && field.schema.hint.length > 38);

                    return (
                      <Col
                        key={field.key}
                        xs={24}
                        lg={isLongField ? 24 : 12}
                      >
                        <FieldRenderer
                          fieldKey={field.key}
                          fieldSchema={field.schema}
                          value={field.value}
                          templateCdnBaseUrl={templateCdnBaseUrl}
                          providers={providers}
                          personas={personas}
                          fullKeyPath={`${activeCategory}.${field.key}`}
                          error={errors[activeCategory]?.[field.key]}
                          subErrors={errors[activeCategory]}
                          onChange={(newVal) =>
                            handleFieldChange(activeCategory, field.key, newVal)
                          }
                        />
                      </Col>
                    );
                  })}
                </Row>
              )}
            </Col>
          </Row>
        </Spin>
      </Card>
      <Modal title="重新读取会替换未保存的修改" open={reloadConfirmationOpen} onCancel={cancelReload} onOk={confirmReload} okText="舍弃修改并重新读取" cancelText="继续编辑" okButtonProps={{ danger: true }}>
        <Paragraph>配置中心还有未保存的草稿。重新读取会使用服务器上的已保存配置替换这些修改。</Paragraph>
      </Modal>
      <Drawer
        title={<Space wrap><span>{wordCloudScope ? `本群词云 · ${wordCloudScope.split(":GroupMessage:")[1]}` : "全局词云外观编辑器"}</span>{wordCloudDirty && <Tag color="warning">词云有未保存修改</Tag>}</Space>}
        open={wordCloudEditorOpen}
        onClose={() => { setWordCloudEditorOpen(false); setWordCloudCatalogRevision((current) => current + 1); }}
        width="min(1480px, 100vw)"
        destroyOnHidden
        styles={{ body: { padding: isMobileScreen ? 16 : 24 } }}
        extra={<Space wrap>
          <Popconfirm title="恢复词云上次保存的设置？" description="词云的全局设置和群级覆盖将恢复，其他分组的草稿会保留。" okText="恢复" cancelText="取消" onConfirm={restoreSavedWordCloud} disabled={!wordCloudDirty || saving}>
            <Button icon={<UndoOutlined />} disabled={!wordCloudDirty || saving}>撤销词云修改</Button>
          </Popconfirm>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving} disabled={!isDirty || loading || !configLoaded}>保存配置</Button>
        </Space>}
      >
        <WordCloudEditor key={wordCloudScope || "global"} value={editorValue} onChange={(key, value) => patchEditor({ [key]: value })} onPatch={patchEditor} protectedFonts={protectedFonts} scopeUmo={wordCloudScope} overrideKeys={wordCloudScope ? Object.keys(scopedObject) : undefined} disabled={saving || loading || !configLoaded} />
      </Drawer>
    </div>
  );
};
