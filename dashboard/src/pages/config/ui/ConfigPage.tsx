import React from "react";
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
} from "antd";
import {
  SaveOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { useConfigViewModel } from "../model/useConfigViewModel";
import { FieldRenderer } from "../../../widgets/config-form/ui/FieldRenderer";
import { useTheme } from "../../../shared/lib/useTheme";

const { Title, Text, Paragraph } = Typography;

interface ConfigPageProps {
  viewModel: ReturnType<typeof useConfigViewModel>;
}

export const ConfigPage: React.FC<ConfigPageProps> = ({ viewModel }) => {
  const { isDark } = useTheme();
  const {
    loading,
    saving,
    isDirty,
    categories,
    providers,
    personas,
    activeCategory,
    currentGroupFields,
    activeGroupMeta,
    searchQuery,
    setSearchQuery,
    setActiveCategory,
    handleFieldChange,
    handleSave,
    handleReload,
  } = viewModel;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部概览与全局操作栏 (Header Bar) */}
      <Card size="small">
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

          <Space size="small">
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
              disabled={!isDirty || loading}
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
            {/* 左侧：搜索与分组导航 */}
            <Col
              xs={24}
              md={6}
              style={{
                borderRight: `1px solid ${isDark ? "#303030" : "#f0f0f0"}`,
                padding: "16px 12px",
                background: isDark ? "#141414" : "#fafafa",
              }}
            >
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

                  if (!isVisible) return null;

                  return (
                    <div
                      key={cat.key}
                      onClick={() => setActiveCategory(cat.key)}
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
                      {cat.matchCount !== undefined ? (
                        <Badge
                          count={cat.matchCount}
                          style={{
                            backgroundColor: isActive ? "#ffffff" : "#1677ff",
                            color: isActive ? "#1677ff" : "#ffffff",
                          }}
                        />
                      ) : (
                        <Text
                          style={{
                            fontSize: 11,
                            color: isActive ? "rgba(255, 255, 255, 0.75)" : "#8c8c8c",
                          }}
                        >
                          {cat.totalFields} 项
                        </Text>
                      )}
                    </div>
                  );
                })}
              </div>
            </Col>

            {/* 右侧：分组详情与表单项 */}
            <Col xs={24} md={18} style={{ padding: "20px 24px" }}>
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
                  <div>
                    <Title level={4} style={{ margin: 0, fontSize: 16 }}>
                      {activeGroupMeta.description || activeCategory}
                    </Title>
                    {activeGroupMeta.hint && (
                      <Text
                        type="secondary"
                        style={{ fontSize: 12, display: "block", marginTop: 4 }}
                      >
                        {activeGroupMeta.hint}
                      </Text>
                    )}
                  </div>
                  <Tag color="default" style={{ margin: 0 }}>
                    字段数: {currentGroupFields.length}
                  </Tag>
                </div>
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
              ) : (
                <Row gutter={[16, 0]}>
                  {currentGroupFields.map((field) => {
                    const isLongField =
                      field.schema.type === "template_list" ||
                      field.schema.type === "object" ||
                      field.schema.type === "list" ||
                      field.schema.type === "text" ||
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
                          providers={providers}
                          personas={personas}
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
    </Space>
  );
};
