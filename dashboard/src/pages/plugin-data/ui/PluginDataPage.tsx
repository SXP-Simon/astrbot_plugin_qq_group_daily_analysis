import React, { useEffect } from "react";
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
  Alert,
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
import { MetricCard } from "../../../shared/ui/MetricCard";
import { formatBytes } from "../../../shared/lib/formatters";
import { usePluginDataViewModel } from "../model/usePluginDataViewModel";

const { Text } = Typography;

// 统一现代无衬线等宽/数字字体规范，杜绝宋体/Courier等衬线体
const SANS_NUM_STYLE: React.CSSProperties = {
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  fontVariantNumeric: "tabular-nums",
  fontWeight: 600,
  fontSize: 13,
};

interface PartitionItem {
  key: string;
  name: string;
  icon: React.ReactNode;
  pathTag: string;
  count: number;
  sizeBytes: number;
  description: string;
  impactNotice: string;
  onClear: () => void;
  clearKey: string;
}

export const PluginDataPage: React.FC = () => {
  const vm = usePluginDataViewModel();

  useEffect(() => {
    vm.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { overview, loading, clearing } = vm;

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
      name: "自定义模板备份",
      icon: <AppstoreOutlined style={{ color: "#722ed1" }} />,
      pathTag: "plugin_data/custom_t2i_templates/",
      count: overview.custom_templates.count,
      sizeBytes: overview.custom_templates.size_bytes,
      description: "用户个性化修改过的 T2I 报告模板备份与覆盖文件。",
      impactNotice: "清理后自定义模板备份将重置，插件升级后将自动还原为官方默认样式。",
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

  const columns = [
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
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部统计卡片矩阵 (KPI Grid - 7项指标自适应) */}
      <Row gutter={[10, 10]}>
        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="数据总占用"
            value={formatBytes(totalBytes)}
            prefix={<HddOutlined style={{ color: "#2563eb" }} />}
            subTitle={`共计 ${totalFiles.toLocaleString()} 个文件`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="临时渲染缓存"
            value={formatBytes(overview.temp_files.size_bytes)}
            prefix={<FileZipOutlined style={{ color: "#fa8c16" }} />}
            subTitle={`${overview.temp_files.count.toLocaleString()} 个临时文件`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="历史报告文件"
            value={formatBytes(overview.reports.size_bytes)}
            prefix={<FileImageOutlined style={{ color: "#52c41a" }} />}
            subTitle={`${overview.reports.count.toLocaleString()} 份报告存档`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="群成员头像缓存"
            value={formatBytes(overview.avatars.size_bytes)}
            prefix={<UserOutlined style={{ color: "#1677ff" }} />}
            subTitle={`${overview.avatars.count.toLocaleString()} 个用户头像`}
            loading={loading}
          />
        </Col>

        <Col xs={12} sm={8} md={4}>
          <MetricCard
            title="配置自动备份"
            value={formatBytes(overview.config_backups.size_bytes)}
            prefix={<HistoryOutlined style={{ color: "#eb2f96" }} />}
            subTitle={`${overview.config_backups.count.toLocaleString()} 份历史备份`}
            loading={loading}
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
            subTitle={`${(overview.custom_templates.count + overview.config_files.count).toLocaleString()} 个模板/素材`}
            loading={loading}
          />
        </Col>
      </Row>

      {/* 核心分区明细与管理表格 */}
      <Card
        size="small"
        title={
          <Space size={8}>
            <FolderOpenOutlined style={{ color: "#2563eb" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              存储空间全景与分区独立管理
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
              icon={<ReloadOutlined spin={loading} />}
              onClick={vm.refresh}
              loading={loading}
            >
              刷新概览
            </Button>
          </Space>
        }
      >
        <Table<PartitionItem>
          rowKey="key"
          columns={columns}
          dataSource={partitions}
          pagination={false}
          size="small"
          loading={loading}
          style={{ width: "100%" }}
        />
      </Card>

      {/* 底部提示卡片 */}
      <Alert
        message="存储健康与归档说明"
        description={
          <div style={{ fontSize: 12, lineHeight: "1.6" }}>
            各分区支持单独安全清空，防呆气泡确认可避免误删核心文件。如需管理
            <strong>链路追踪 SQLite 数据库 (traces.db)</strong>
            ，请前往「分析记录」标签页；如需清空
            <strong>运行日志缓冲</strong>，请前往「运行日志」标签页。
          </div>
        }
        type="info"
        showIcon
        style={{ fontSize: 12 }}
      />
    </Space>
  );
};
