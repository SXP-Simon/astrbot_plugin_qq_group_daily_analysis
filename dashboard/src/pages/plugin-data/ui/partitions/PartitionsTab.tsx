import React from "react";
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Popconfirm,
  Tag,
  Typography,
  Space,
  Progress,
  Tooltip,
} from "antd";
import {
  DeleteOutlined,
  ReloadOutlined,
  UserOutlined,
  FileImageOutlined,
  FileZipOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  HddOutlined,
  InfoCircleOutlined,
  FolderOpenOutlined,
  HistoryOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../../shared/ui/MetricCard";
import { formatBytes } from "../../../../shared/lib/formatters";
import { usePluginDataViewModel } from "../../model/usePluginDataViewModel";
import { SANS_NUM_STYLE, PartitionItem } from "../constants";

const { Text } = Typography;

interface PartitionsTabProps {
  vm: ReturnType<typeof usePluginDataViewModel>;
}

export const PartitionsTab: React.FC<PartitionsTabProps> = ({ vm }) => {
  const { overview, loadingOverview, clearing } = vm;

  const totalBytes =
    overview.avatars.size_bytes +
    overview.custom_templates.size_bytes +
    overview.config_files.size_bytes +
    overview.config_backups.size_bytes +
    overview.reports.size_bytes +
    overview.temp_files.size_bytes;

  const totalFiles =
    overview.avatars.count +
    overview.custom_templates.count +
    overview.config_files.count +
    overview.config_backups.count +
    overview.reports.count +
    overview.temp_files.count;

  // 存储空间全景分区列表
  const partitions: PartitionItem[] = [
    {
      key: "temp_files",
      name: "临时渲染缓存",
      icon: <FileZipOutlined style={{ color: "#fa8c16" }} />,
      pathTag: "data/temp/io_temp_img_*",
      count: overview.temp_files.count,
      sizeBytes: overview.temp_files.size_bytes,
      description: "报告/图片渲染过程产生的高清中间态与输出缓存。",
      impactNotice: "安全无损。分析流程已完成后可随时清理，不影响历史记录。",
      clearKey: "temp_files",
      onClear: vm.clearTempFiles,
    },
    {
      key: "avatars",
      name: "群成员头像缓存",
      icon: <UserOutlined style={{ color: "#1677ff" }} />,
      pathTag: "plugin_data/cache/avatars/",
      count: overview.avatars.count,
      sizeBytes: overview.avatars.size_bytes,
      description: "群成员头像二进制图片，用于报告内嵌头像与话题发言人展示。",
      impactNotice: "清理后本地文件被删除，下次生成日报时会自动按需重新拉取。",
      clearKey: "avatars",
      onClear: vm.clearAvatarCache,
    },
    {
      key: "reports",
      name: "历史报告文件",
      icon: <FileImageOutlined style={{ color: "#52c41a" }} />,
      pathTag: "report_output_dir (jpg/png/html)",
      count: overview.reports.count,
      sizeBytes: overview.reports.size_bytes,
      description: "各群聊已生成的日报图片长图与 HTML 网页离线报告存档。",
      impactNotice: "清理后历史报告页将无法预览已删除的图文文件，但不影响 Trace 统计。",
      clearKey: "reports",
      onClear: vm.clearReports,
    },
    {
      key: "config_backups",
      name: "配置自动备份",
      icon: <HistoryOutlined style={{ color: "#eb2f96" }} />,
      pathTag: "plugin_data/config_backups/",
      count: overview.config_backups.count,
      sizeBytes: overview.config_backups.size_bytes,
      description: "版本升级或旧版配置迁移时自动留存的历次配置历史备份副本。",
      impactNotice: "清理后释放备份存储空间，当前生效的插件配置不会受任何影响。",
      clearKey: "config_backups",
      onClear: vm.clearConfigBackups,
    },
    {
      key: "custom_templates",
      name: "自定义报告模板",
      icon: <AppstoreOutlined style={{ color: "#722ed1" }} />,
      pathTag: "plugin_data/custom_t2i_templates/reporting_templates/",
      count: overview.custom_templates.count,
      sizeBytes: overview.custom_templates.size_bytes,
      description: "用户安装或上传的第三方/自定义 T2I 报告主题模板。",
      impactNotice: "清理后已安装的自定义报告模板将被移除，报告将使用官方内置主题渲染。",
      clearKey: "custom_templates",
      onClear: vm.clearCustomTemplates,
    },
    {
      key: "config_files",
      name: "配置参考素材",
      icon: <FileTextOutlined style={{ color: "#13c2c2" }} />,
      pathTag: "plugin_data/files/",
      count: overview.config_files.count,
      sizeBytes: overview.config_files.size_bytes,
      description: "在配置中心中上传的角色立绘、漫画参考图等持久化素材。",
      impactNotice: "清理后配置中引用的图片文件将失效，需重新在配置中心上传。",
      clearKey: "config_files",
      onClear: vm.clearConfigFiles,
    },
  ];

  const partitionColumns = [
    {
      title: "数据分区",
      dataIndex: "name",
      key: "name",
      width: 220,
      render: (_: string, item: PartitionItem) => (
        <Space direction="vertical" size={2}>
          <Space size={6}>
            <span style={{ fontSize: 16 }}>{item.icon}</span>
            <Text strong style={{ fontSize: 13 }}>
              {item.name}
            </Text>
          </Space>
          <Tooltip title={`物理存储路径: ${item.pathTag}`}>
            <Tag
              style={{
                fontSize: 11,
                fontFamily:
                  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                margin: 0,
                cursor: "pointer",
                maxWidth: 200,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {item.pathTag}
            </Tag>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: "文件数量",
      dataIndex: "count",
      key: "count",
      width: 110,
      align: "right" as const,
      render: (count: number) => (
        <span style={SANS_NUM_STYLE}>{count.toLocaleString()}</span>
      ),
    },
    {
      title: "占用空间",
      dataIndex: "sizeBytes",
      key: "sizeBytes",
      width: 120,
      align: "right" as const,
      render: (bytes: number) => (
        <span
          style={{
            ...SANS_NUM_STYLE,
            color: bytes > 0 ? undefined : "#8c8c8c",
          }}
        >
          {formatBytes(bytes)}
        </span>
      ),
    },
    {
      title: "空间占比",
      key: "ratio",
      width: 140,
      render: (_: unknown, item: PartitionItem) => {
        const percent =
          totalBytes > 0
            ? Math.round((item.sizeBytes / totalBytes) * 100)
            : 0;
        return (
          <div style={{ width: 110 }}>
            <Progress
              percent={percent}
              size="small"
              strokeColor="#2563eb"
              format={(pct) => (
                <span
                  style={{
                    fontSize: 11,
                    fontFamily:
                      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {pct}%
                </span>
              )}
            />
          </div>
        );
      },
    },
    {
      title: "分区用途与清理影响",
      key: "description",
      ellipsis: true,
      render: (_: unknown, item: PartitionItem) => (
        <Space direction="vertical" size={2} style={{ width: "100%" }}>
          <Text style={{ fontSize: 12 }}>{item.description}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            <InfoCircleOutlined style={{ marginRight: 4 }} />
            {item.impactNotice}
          </Text>
        </Space>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      align: "center" as const,
      render: (_: unknown, item: PartitionItem) => {
        const isClearing = clearing === item.clearKey;
        const isEmpty = item.count === 0 && item.sizeBytes === 0;

        return (
          <Popconfirm
            title={`确认清空「${item.name}」？`}
            description={
              <div style={{ maxWidth: 260 }}>
                <p style={{ margin: 0, fontSize: 12 }}>{item.impactNotice}</p>
                <p style={{ margin: "4px 0 0 0", color: "#ff4d4f", fontSize: 12 }}>
                  此操作将删除该分区所有文件且不可撤销。
                </p>
              </div>
            }
            okText="确认清空"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
            onConfirm={item.onClear}
            disabled={isClearing || isEmpty}
          >
            <Button
              danger
              size="small"
              type="primary"
              ghost
              icon={<DeleteOutlined />}
              loading={isClearing}
              disabled={isEmpty}
              style={{ fontSize: 12 }}
            >
              清空
            </Button>
          </Popconfirm>
        );
      },
    },
  ];

  return (
    <>
      <Row gutter={[10, 10]}>
        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="数据总占用"
            value={formatBytes(totalBytes)}
            prefix={<HddOutlined style={{ color: "#2563eb" }} />}
            subTitle={`共计 ${totalFiles.toLocaleString()} 个文件`}
            loading={loadingOverview}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="临时渲染缓存"
            value={formatBytes(overview.temp_files.size_bytes)}
            prefix={<FileZipOutlined style={{ color: "#fa8c16" }} />}
            subTitle={`${overview.temp_files.count.toLocaleString()} 个临时文件`}
            loading={loadingOverview}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="历史报告文件"
            value={formatBytes(overview.reports.size_bytes)}
            prefix={<FileImageOutlined style={{ color: "#52c41a" }} />}
            subTitle={`${overview.reports.count.toLocaleString()} 份报告存档`}
            loading={loadingOverview}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="群成员头像缓存"
            value={formatBytes(overview.avatars.size_bytes)}
            prefix={<UserOutlined style={{ color: "#1677ff" }} />}
            subTitle={`${overview.avatars.count.toLocaleString()} 个用户头像`}
            loading={loadingOverview}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="配置自动备份"
            value={formatBytes(overview.config_backups.size_bytes)}
            prefix={<HistoryOutlined style={{ color: "#eb2f96" }} />}
            subTitle={`${overview.config_backups.count.toLocaleString()} 份历史备份`}
            loading={loadingOverview}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="自定义模板与素材"
            value={formatBytes(
              overview.custom_templates.size_bytes +
                overview.config_files.size_bytes
            )}
            prefix={<AppstoreOutlined style={{ color: "#722ed1" }} />}
            subTitle={`${(
              overview.custom_templates.count +
              overview.config_files.count
            ).toLocaleString()} 个模板/素材`}
            loading={loadingOverview}
          />
        </Col>
      </Row>

      <Card
        size="small"
        title={
          <Space size={8}>
            <FolderOpenOutlined style={{ color: "#2563eb" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              存储分区明细与管理
            </span>
            <Tag
              color="blue"
              style={{
                fontSize: 11,
                fontFamily:
                  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
              }}
            >
              6 个存储分区
            </Tag>
          </Space>
        }
        extra={
          <Space size={8}>
            <Button
              size="small"
              icon={<ReloadOutlined spin={loadingOverview} />}
              onClick={vm.refreshOverview}
              loading={loadingOverview}
            >
              刷新概览
            </Button>
          </Space>
        }
      >
        <Table<PartitionItem>
          rowKey="key"
          columns={partitionColumns}
          dataSource={partitions}
          pagination={false}
          size="small"
          loading={loadingOverview}
          scroll={{ x: 750 }}
          style={{ width: "100%" }}
        />
      </Card>
    </>
  );
};
