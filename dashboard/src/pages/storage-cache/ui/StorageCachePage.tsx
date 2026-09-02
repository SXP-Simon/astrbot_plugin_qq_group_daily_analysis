import React from "react";
import {
  Card,
  Table,
  Button,
  Select,
  Input,
  Space,
  Tag,
  Row,
  Col,
  Typography,
  Tooltip,
  Popconfirm,
  Alert,
  Dropdown,
  Spin,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  ReloadOutlined,
  ThunderboltOutlined,
  DeleteOutlined,
  SearchOutlined,
  DatabaseOutlined,
  FolderOpenOutlined,
  FileZipOutlined,
  PictureOutlined,
  FileTextOutlined,
  CopyOutlined,
  LoadingOutlined,
  DownOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import { useStorageCacheViewModel } from "../model/useStorageCacheViewModel";
import { ResourceCacheItem } from "../../../entities/resource/model/types";

const { Text } = Typography;

export const StorageCachePage: React.FC = () => {
  const {
    storage,
    stats,
    resources,
    allResourcesCount,
    loading,
    prefetchProgress,
    clearing,
    selectedTemplate,
    setSelectedTemplate,
    selectedCategory,
    setSelectedCategory,
    searchQuery,
    setSearchQuery,
    availableTemplates,
    refresh,
    handlePrefetch,
    handleClear,
  } = useStorageCacheViewModel();

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success("资源链接已复制到剪贴板");
  };

  const isSelectedSpecific = selectedTemplate && selectedTemplate !== "all";
  const selectedTemplateObj = availableTemplates.find(
    (t) => t.id === selectedTemplate
  );

  // 更多预取菜单选项
  const prefetchMenuItems = [
    {
      key: "all",
      label: "全量预取所有模板静态资源",
      icon: <ThunderboltOutlined style={{ color: "#d97706" }} />,
      onClick: () => handlePrefetch("all"),
    },
    { type: "divider" as const },
    ...availableTemplates.map((t) => ({
      key: t.id,
      label: `预取 ${t.label}`,
      onClick: () => handlePrefetch(t.id),
    })),
  ];

  // 表格列定义
  const columns: ColumnsType<ResourceCacheItem> = [
    {
      title: "模板归属",
      dataIndex: "template",
      key: "template",
      width: 130,
      render: (tmpl: string) => (
        <Tag
          bordered
          style={{
            fontFamily: "monospace",
            fontSize: 11,
            margin: 0,
            borderRadius: 4,
          }}
        >
          {tmpl || "global"}
        </Tag>
      ),
    },
    {
      title: "资源分类",
      dataIndex: "category",
      key: "category",
      width: 90,
      render: (cat: string) => {
        let color = "default";
        if (cat === "fonts") color = "warning";
        else if (cat === "css") color = "processing";
        else if (cat === "scripts") color = "purple";
        else if (cat === "images") color = "success";

        return (
          <Tag
            color={color}
            bordered
            style={{
              fontFamily: "monospace",
              fontSize: 11,
              margin: 0,
              borderRadius: 4,
            }}
          >
            {cat}
          </Tag>
        );
      },
    },
    {
      title: "远程资源 URL",
      dataIndex: "url",
      key: "url",
      ellipsis: true,
      render: (url: string) => (
        <Tooltip title={url} placement="topLeft">
          <Text
            copyable={{ text: url }}
            style={{
              fontFamily: "monospace",
              fontSize: 12,
              color: "#1e293b",
            }}
          >
            {url}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: "MIME 类型",
      dataIndex: "mime_type",
      key: "mime_type",
      width: 140,
      render: (mime: string) => (
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 11,
            color: "#64748b",
          }}
        >
          {mime || "application/octet-stream"}
        </span>
      ),
    },
    {
      title: "本地大小",
      dataIndex: "size",
      key: "size",
      width: 100,
      sorter: (a, b) => a.size - b.size,
      render: (size: number, record: ResourceCacheItem) => (
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 12,
            fontWeight: 500,
            color: "#334155",
          }}
        >
          {record.size_formatted || `${(size / 1024).toFixed(1)} KB`}
        </span>
      ),
    },
    {
      title: "命中次数",
      dataIndex: "access_count",
      key: "access_count",
      width: 90,
      sorter: (a, b) => (a.access_count || 1) - (b.access_count || 1),
      render: (count: number) => (
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 12,
            fontWeight: 600,
            color: "#16a34a",
          }}
        >
          {count || 1}
        </span>
      ),
    },
    {
      title: "本地相对存储路径",
      dataIndex: "relative_path",
      key: "relative_path",
      width: 220,
      ellipsis: true,
      render: (relPath: string, record: ResourceCacheItem) => {
        const display = relPath || record.file_path;
        return (
          <Tooltip title={display} placement="topLeft">
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 11,
                color: "#64748b",
              }}
            >
              {display}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 90,
      align: "right",
      render: (_: any, record: ResourceCacheItem) => (
        <Button
          type="link"
          size="small"
          icon={<CopyOutlined style={{ fontSize: 12 }} />}
          onClick={() => handleCopy(record.url)}
          style={{ padding: "0 4px", fontSize: 12 }}
        >
          复制
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部紧凑控制栏 */}

      <Card
        size="small"
        styles={{
          body: {
            padding: "8px 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 8,
          },
        }}
      >
        <Space wrap align="center">
          <DatabaseOutlined style={{ color: "#2563eb", fontSize: 16 }} />
          <span style={{ fontWeight: 600, fontSize: 13, color: "#1e293b" }}>
            存储空间全景与静态资源缓存控制台
          </span>
          <Tag
            color="success"
            bordered
            style={{
              borderRadius: 4,
              fontSize: 11,
              fontFamily: "monospace",
              margin: 0,
            }}
          >
            ● 0 外网请求拦截就绪
          </Tag>
        </Space>

        <Space wrap align="center" size="small">
          <Button
            size="small"
            icon={<ReloadOutlined spin={loading} />}
            onClick={() => refresh(true)}
            style={{ fontSize: 12, borderRadius: 4 }}
          >
            刷新
          </Button>

          {/* 细粒度模板预取与全量预取组合按键 */}
          <Space.Compact size="small">
            <Button
              type="primary"
              size="small"
              icon={
                prefetchProgress.active ? (
                  <LoadingOutlined />
                ) : (
                  <ThunderboltOutlined />
                )
              }
              loading={prefetchProgress.active}
              onClick={() =>
                handlePrefetch(
                  isSelectedSpecific ? selectedTemplate : "all"
                )
              }
              style={{
                fontSize: 12,
                borderRadius: "4px 0 0 4px",
                backgroundColor: "#2563eb",
                fontWeight: 500,
              }}
            >
              {isSelectedSpecific
                ? `预取 ${selectedTemplateObj?.label || selectedTemplate}`
                : "全量预取所有模板"}
            </Button>
            <Dropdown
              menu={{ items: prefetchMenuItems }}
              placement="bottomRight"
              disabled={prefetchProgress.active}
            >
              <Button
                type="primary"
                size="small"
                icon={<DownOutlined style={{ fontSize: 10 }} />}
                style={{
                  borderRadius: "0 4px 4px 0",
                  backgroundColor: "#1d4ed8",
                  padding: "0 6px",
                }}
              />
            </Dropdown>
          </Space.Compact>

          <Popconfirm
            title="确认清理静态资源缓存？"
            description={
              isSelectedSpecific
                ? `将清理模板 [${selectedTemplateObj?.label || selectedTemplate}] 下的所有已缓存静态资源`
                : "将清空全部已缓存的字体、样式表和图片资源"
            }
            onConfirm={() => handleClear()}
            okText="确认清理"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={clearing}
              style={{ fontSize: 12, borderRadius: 4, fontWeight: 500 }}
            >
              {isSelectedSpecific
                ? `清理 [${selectedTemplateObj?.label || selectedTemplate}] 缓存`
                : "清理全部缓存"}
            </Button>
          </Popconfirm>
        </Space>
      </Card>

      {/* 友好预取进度提示 */}
      {prefetchProgress.active && (
        <Alert
          type="info"
          showIcon
          icon={<LoadingOutlined style={{ color: "#2563eb", fontSize: 15 }} />}
          message={
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              <span>正在预取【{prefetchProgress.templateName}】的外部字体与样式表...</span>
              <span style={{ fontFamily: "monospace", color: "#2563eb" }}>
                已耗时：{prefetchProgress.elapsedSeconds} 秒
              </span>
            </div>
          }
          description={
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
              系统正在从高速网络拉取字体切片并写入本地磁盘持久化，保证后续渲染 0 网络请求，请耐心等待...
            </div>
          }
          style={{
            borderRadius: 6,
            border: "1px solid #bfdbfe",
            backgroundColor: "#eff6ff",
            padding: "8px 14px",
          }}
        />
      )}

      {/* 1. Plugin Data 存储空间指标矩阵 (KPI Matrix) */}
      <Row gutter={[10, 10]}>
        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="数据目录总空间"
            value={storage?.total?.mb ?? 0}
            suffix="MB"
            prefix={<FolderOpenOutlined style={{ color: "#2563eb" }} />}
            subTitle={`${storage?.total?.files ?? 0} 个文件`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="静态资源与字体缓存"
            value={storage?.resources_cache?.mb ?? 0}
            suffix="MB"
            prefix={<FileZipOutlined style={{ color: "#d97706" }} />}
            subTitle={`${storage?.resources_cache?.files ?? 0} 个文件`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="链路数据库 (Traces)"
            value={storage?.database?.traces_sqlite_mb ?? 0}
            suffix="MB"
            prefix={<DatabaseOutlined style={{ color: "#2563eb" }} />}
            subTitle="SQLite 链路记录"
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="历史报告与图片"
            value={storage?.reports?.mb ?? 0}
            suffix="MB"
            prefix={<PictureOutlined style={{ color: "#9333ea" }} />}
            subTitle={`${storage?.reports?.files ?? 0} 份产物报告`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="断点与增量记录"
            value={storage?.checkpoints?.mb ?? 0}
            suffix="MB"
            prefix={<FileTextOutlined style={{ color: "#16a34a" }} />}
            subTitle={`${storage?.checkpoints?.files ?? 0} 项检查点`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="用户头像缓存"
            value={storage?.avatars?.mb ?? 0}
            suffix="MB"
            prefix={<PictureOutlined style={{ color: "#06b6d4" }} />}
            subTitle={`${storage?.avatars?.files ?? 0} 张头像`}
            loading={loading}
          />
        </Col>
      </Row>

      {/* 2. 静态资源与字体缓存看板 */}
      <Card
        size="small"
        title={
          <Space wrap align="center" size="small">
            <span style={{ fontWeight: 600, fontSize: 13, color: "#1e293b" }}>
              模板资源缓存
            </span>

            {/* 完整模板筛选下拉 */}
            <Select
              size="small"
              value={selectedTemplate}
              onChange={setSelectedTemplate}
              style={{ width: 170, fontSize: 12 }}
              options={[
                { label: "全部模板", value: "all" },
                { label: "global (通用)", value: "global" },
                ...availableTemplates.map((t) => ({
                  label: t.label,
                  value: t.id,
                })),
              ]}
            />

            {/* 分类筛选下拉 */}
            <Select
              size="small"
              value={selectedCategory}
              onChange={setSelectedCategory}
              style={{ width: 130, fontSize: 12 }}
              options={[
                { label: "全部分类", value: "all" },
                {
                  label: `字体 (${stats?.by_category?.fonts?.files ?? 0})`,
                  value: "fonts",
                },
                {
                  label: `CSS (${stats?.by_category?.css?.files ?? 0})`,
                  value: "css",
                },
                {
                  label: `图片 (${stats?.by_category?.images?.files ?? 0})`,
                  value: "images",
                },
                {
                  label: `脚本 (${stats?.by_category?.scripts?.files ?? 0})`,
                  value: "scripts",
                },
              ]}
            />

            {/* 搜索框 */}
            <Input
              size="small"
              placeholder="搜索 URL / 路径 / MIME..."
              prefix={<SearchOutlined style={{ color: "#94a3b8" }} />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              style={{ width: 220, fontSize: 12 }}
            />
          </Space>
        }
        extra={
          <Space size="middle" style={{ fontSize: 12, color: "#64748b" }}>
            <span>
              已加载{" "}
              <strong style={{ fontFamily: "monospace", color: "#1e293b" }}>
                {resources.length}
              </strong>{" "}
              / {allResourcesCount} 项
            </span>
            <span>
              总命中访问{" "}
              <strong style={{ fontFamily: "monospace", color: "#16a34a" }}>
                {stats?.total_access_count ?? 0}
              </strong>{" "}
              次
            </span>
          </Space>
        }
        styles={{ body: { padding: 0 } }}
      >
        <Table<ResourceCacheItem>
          columns={columns}
          dataSource={resources}
          rowKey="hash"
          size="small"
          loading={loading}
          pagination={{
            size: "small",
            showSizeChanger: true,
            defaultPageSize: 20,
            pageSizeOptions: ["10", "20", "50", "100"],
            showTotal: (total) => `共 ${total} 项缓存资源`,
            style: { padding: "8px 16px", margin: 0 },
          }}
          scroll={{ x: 900 }}
          locale={{
            emptyText: (
              <div style={{ padding: 32, textAlign: "center", color: "#94a3b8", fontSize: 12 }}>
                暂无已缓存资源。在日常分析实际渲染时将自动按需缓存；亦可点击上方按钮手动预取。
              </div>
            ),
          }}
        />
      </Card>
    </Space>
  );
};
