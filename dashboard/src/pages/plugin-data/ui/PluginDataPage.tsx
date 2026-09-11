import React, { useEffect, useState } from "react";
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
  Tabs,
  Select,
  Input,
  Modal,
  message,
  Empty,
  Badge,
  theme,
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
  ThunderboltOutlined,
  SaveOutlined,
  EyeOutlined,
  CopyOutlined,
  ClearOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { MetricCard } from "../../../shared/ui/MetricCard";
import {
  formatBytes,
  formatTimestamp,
  formatTokens,
  formatStageName,
} from "../../../shared/lib/formatters";
import { usePluginDataViewModel } from "../model/usePluginDataViewModel";
import {
  IncrementalBatchItem,
  CheckpointItem,
} from "../../../entities/plugin-data/model/types";

const { Text, Paragraph } = Typography;

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

const getStageMeta = (stage: string): { label: string; color: string } => {
  const label = formatStageName(stage);
  const colorMap: Record<string, string> = {
    FETCH_MESSAGES: "blue",
    CLEAN_MESSAGES: "geekblue",
    STATS_ANALYSIS: "orange",
    LLM_ANALYSIS: "purple",
    SAVE_SUMMARY: "gold",
    RENDER_REPORT: "cyan",
    DISPATCH_REPORT: "green",
    COMIC_STORYBOARD: "magenta",
    COMIC_DRAWING: "volcano",
    CRASH_RECOVERY: "red",
  };
  return {
    label,
    color: colorMap[stage] || colorMap[stage.toUpperCase()] || "default",
  };
};

export const PluginDataPage: React.FC = () => {
  const { token } = theme.useToken();
  const vm = usePluginDataViewModel();
  const [activeTab, setActiveTab] = useState<string>("partitions");

  useEffect(() => {
    vm.refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当切换到增量 Tab 时，若未选中群但有群列表，则自动加载
  useEffect(() => {
    if (activeTab === "incremental") {
      if (vm.selectedIncrGroup) {
        vm.loadIncrementalData(vm.selectedIncrGroup);
      } else if (vm.incrGroups.length > 0) {
        vm.handleSelectIncrGroup(vm.incrGroups[0]);
      }
    } else if (activeTab === "checkpoints") {
      vm.loadCheckpoints();
      vm.refreshCheckpointGroups();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const {
    overview,
    loadingOverview,
    clearing,
    incrGroups,
    selectedIncrGroup,
    incrBatches,
    incrCursor,
    loadingIncremental,
    batchDetailModalOpen,
    selectedBatchDetail,
    loadingBatchDetail,
    ckptGroups,
    ckptFilterGroup,
    ckptFilterDate,
    ckptFilterStage,
    checkpoints,
    checkpointsTotal,
    checkpointsPage,
    checkpointsPageSize,
    loadingCheckpoints,
    ckptDetailModalOpen,
    selectedCkptDetail,
    loadingCkptDetail,
  } = vm;

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

  // 1. 存储空间全景分区
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

  // 2. 增量分析批次表格定义
  const batchColumns = [
    {
      title: "批次 ID",
      dataIndex: "batch_id",
      key: "batch_id",
      width: 140,
      render: (batchId: string) => (
        <Tag
          color="blue"
          style={{
            ...SANS_NUM_STYLE,
            fontWeight: 500,
            fontSize: 12,
            margin: 0,
          }}
        >
          {batchId}
        </Tag>
      ),
    },
    {
      title: "生成时间",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 160,
      render: (ts: number) => (
        <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: "消息数 / 字符",
      key: "msg_stats",
      width: 130,
      render: (_: unknown, item: IncrementalBatchItem) => (
        <Space size={4}>
          <Badge
            count={item.messages_count}
            overflowCount={999999}
            style={{ backgroundColor: "#1677ff", fontSize: 11 }}
          />
          <Text type="secondary" style={{ fontSize: 11 }}>
            ({(item.characters_count || 0).toLocaleString()} 字)
          </Text>
        </Space>
      ),
    },
    {
      title: "提炼话题概览",
      dataIndex: "topics",
      key: "topics",
      ellipsis: true,
      render: (topics: IncrementalBatchItem["topics"]) => {
        if (!topics || topics.length === 0) {
          return <Text type="secondary" style={{ fontSize: 12 }}>无提炼话题</Text>;
        }
        return (
          <Space wrap size={[4, 4]}>
            {topics.map((t, idx) => (
              <Tag
                key={idx}
                color={
                  (t.heat_score || 0) >= 80
                    ? "volcano"
                    : (t.heat_score || 0) >= 50
                    ? "orange"
                    : "geekblue"
                }
                style={{ fontSize: 11, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {t.title || "未命名话题"} ({t.heat_score || 0}℃)
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: "Token 消耗",
      key: "token_usage",
      width: 120,
      render: (_: unknown, item: IncrementalBatchItem) => {
        const total = item.token_usage?.total_tokens;
        return (
          <span style={SANS_NUM_STYLE}>
            {total ? formatTokens(total) : "-"}
          </span>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 140,
      align: "center" as const,
      render: (_: unknown, item: IncrementalBatchItem) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={() => vm.handleOpenBatchDetail(item)}
            style={{ fontSize: 12 }}
          >
            详情
          </Button>
          <Popconfirm
            title="确认删除该增量批次？"
            description="删除后该批次的话题与统计数据将不再参与汇总计算。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
            onConfirm={() =>
              vm.handleDeleteBatch(item.group_id, item.batch_id)
            }
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              style={{ fontSize: 12 }}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 3. 阶段产物 Checkpoint 表格定义
  const ckptColumns = [
    {
      title: "群聊号码",
      dataIndex: "group_id",
      key: "group_id",
      width: 140,
      render: (gid: string) => <Text strong style={{ fontSize: 13 }}>{gid}</Text>,
    },
    {
      title: "分析归属日期",
      dataIndex: "date_str",
      key: "date_str",
      width: 130,
      render: (d: string) => (
        <Tag color="cyan" style={{ fontSize: 12, ...SANS_NUM_STYLE }}>
          {d}
        </Tag>
      ),
    },
    {
      title: "流水线阶段 (Stage)",
      dataIndex: "stage_name",
      key: "stage_name",
      width: 220,
      render: (stage: string) => {
        const meta = getStageMeta(stage);
        return (
          <Tooltip title={`底层阶段标识: ${stage}`}>
            <Tag color={meta.color} style={{ fontSize: 12 }}>
              {meta.label} ({stage})
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "快照大小",
      key: "data_size",
      width: 110,
      align: "right" as const,
      render: (_: unknown, row: CheckpointItem) => {
        const bytes = row.data_size_bytes ?? row.data_size ?? 0;
        return <span style={SANS_NUM_STYLE}>{formatBytes(bytes)}</span>;
      },
    },
    {
      title: "快照写入时间",
      key: "created_at",
      width: 170,
      render: (_: unknown, row: CheckpointItem) => {
        if (row.created_at_formatted) {
          return (
            <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
              {row.created_at_formatted}
            </span>
          );
        }
        if (typeof row.created_at === "number") {
          return (
            <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
              {formatTimestamp(row.created_at)}
            </span>
          );
        }
        return (
          <span style={{ fontSize: 12, color: token.colorTextSecondary }}>
            {row.created_at || row.updated_at || "-"}
          </span>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 140,
      align: "center" as const,
      render: (_: unknown, item: CheckpointItem) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={() => vm.handleOpenCkptDetail(item)}
            style={{ fontSize: 12 }}
          >
            产物 JSON
          </Button>
          <Popconfirm
            title="确认删除该阶段快照？"
            description="删除后将无法基于此阶段进行断点续跑或零Token重绘。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, size: "small" }}
            cancelButtonProps={{ size: "small" }}
            onConfirm={() =>
              vm.handleDeleteCheckpoint(
                item.group_id,
                item.date_str,
                item.stage_name
              )
            }
          >
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              style={{ fontSize: 12 }}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const handleCopyJson = (data: unknown) => {
    try {
      const jsonStr = JSON.stringify(data, null, 2);
      navigator.clipboard.writeText(jsonStr);
      message.success("已复制 JSON 到剪贴板");
    } catch {
      message.error("复制失败");
    }
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* 顶部标签导航切换 */}
      <Card size="small" bodyStyle={{ padding: "8px 12px" }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: "partitions",
              label: (
                <span>
                  <FolderOpenOutlined /> 存储空间概览
                </span>
              ),
            },
            {
              key: "incremental",
              label: (
                <span>
                  <ThunderboltOutlined /> 增量分析批次 (KV)
                </span>
              ),
            },
            {
              key: "checkpoints",
              label: (
                <span>
                  <SaveOutlined /> 阶段产物快照 (Checkpoints)
                </span>
              ),
            },
          ]}
        />
      </Card>

      {/* 1. 存储空间全景 */}
      {activeTab === "partitions" && (
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
              style={{ width: "100%" }}
            />
          </Card>
        </>
      )}

      {/* 2. 增量分析批次管理 */}
      {activeTab === "incremental" && (
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {/* 群号选择与操作栏 */}
          <Card size="small">
            <Row justify="space-between" align="middle" gutter={[8, 8]}>
              <Col>
                <Space size={12} wrap>
                  <Text strong style={{ fontSize: 13 }}>
                    选择目标群号:
                  </Text>
                  <Select
                    style={{ width: 220 }}
                    value={selectedIncrGroup || undefined}
                    placeholder="请选择含有增量数据的群"
                    onChange={vm.handleSelectIncrGroup}
                    loading={loadingIncremental}
                    options={incrGroups.map((g) => ({ label: `群: ${g}`, value: g }))}
                  />
                  <Button
                    size="small"
                    icon={<ReloadOutlined spin={loadingIncremental} />}
                    onClick={() => {
                      vm.refreshIncrGroups();
                      if (selectedIncrGroup) {
                        vm.loadIncrementalData(selectedIncrGroup);
                      }
                    }}
                  >
                    刷新
                  </Button>
                </Space>
              </Col>

              <Col>
                {selectedIncrGroup && (
                  <Popconfirm
                    title={`确认重置群「${selectedIncrGroup}」的所有增量批次？`}
                    description="此操作将清空该群全部已存储增量 Batch，并将分析游标时间戳重置为 0，下次触发将重新全量拉取分析。"
                    okText="确认重置"
                    cancelText="取消"
                    okButtonProps={{ danger: true, size: "small" }}
                    cancelButtonProps={{ size: "small" }}
                    onConfirm={() => vm.handleResetIncrGroup(selectedIncrGroup)}
                  >
                    <Button
                      danger
                      size="small"
                      type="primary"
                      ghost
                      icon={<ClearOutlined />}
                    >
                      重置本群增量状态
                    </Button>
                  </Popconfirm>
                )}
              </Col>
            </Row>
          </Card>

          {/* 游标状态卡片 */}
          {selectedIncrGroup && incrCursor && (
            <Row gutter={[10, 10]}>
              <Col xs={12} sm={6}>
                <MetricCard
                  title="上次分析推进时间 (游标)"
                  value={
                    incrCursor.last_analyzed_timestamp > 0
                      ? formatTimestamp(incrCursor.last_analyzed_timestamp)
                      : "未分析 (初始 0)"
                  }
                  prefix={<ClockCircleOutlined style={{ color: "#1677ff" }} />}
                  subTitle="增量扫描起始基准时间戳"
                />
              </Col>

              <Col xs={12} sm={6}>
                <MetricCard
                  title="最新包含消息时间"
                  value={
                    incrCursor.last_message_timestamp > 0
                      ? formatTimestamp(incrCursor.last_message_timestamp)
                      : "-"
                  }
                  prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
                  subTitle="最近批次涵盖的最新消息戳"
                />
              </Col>

              <Col xs={12} sm={6}>
                <MetricCard
                  title="已记录去重消息指纹"
                  value={incrCursor.tracked_message_ids_count.toLocaleString()}
                  prefix={<HddOutlined style={{ color: "#722ed1" }} />}
                  subTitle="避免跨批次重复统计的消息 ID 集合"
                />
              </Col>

              <Col xs={12} sm={6}>
                <MetricCard
                  title="累计暂存批次数"
                  value={incrBatches.length.toString()}
                  prefix={<ThunderboltOutlined style={{ color: "#fa8c16" }} />}
                  subTitle="待最终日报合并汇总的批次总数"
                />
              </Col>
            </Row>
          )}

          {/* 批次明细表格 */}
          <Card
            size="small"
            title={
              <Space size={8}>
                <ThunderboltOutlined style={{ color: "#1677ff" }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  {selectedIncrGroup
                    ? `群「${selectedIncrGroup}」暂存增量批次明细`
                    : "增量批次明细"}
                </span>
                {incrBatches.length > 0 && (
                  <Tag color="blue" style={{ fontSize: 11 }}>
                    {incrBatches.length} 个批次
                  </Tag>
                )}
              </Space>
            }
          >
            {selectedIncrGroup ? (
              <Table<IncrementalBatchItem>
                rowKey="batch_id"
                columns={batchColumns}
                dataSource={incrBatches}
                pagination={false}
                size="small"
                loading={loadingIncremental}
                locale={{
                  emptyText: (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="当前群暂无增量批次数据（已汇总为日报或尚未触发增量任务）"
                    />
                  ),
                }}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="请在上方选择群号以查看其增量分析批次"
              />
            )}
          </Card>
        </Space>
      )}

      {/* 3. 阶段产物 Checkpoint 管理 */}
      {activeTab === "checkpoints" && (
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {/* 筛选栏 */}
          <Card size="small">
            <Row gutter={[12, 8]} align="middle">
              <Col xs={24} sm={6} md={5}>
                <Select
                  style={{ width: "100%" }}
                  allowClear
                  placeholder="按群号筛选"
                  value={ckptFilterGroup}
                  onChange={(val) => {
                    vm.setCkptFilterGroup(val);
                    vm.loadCheckpoints(1, checkpointsPageSize, val, ckptFilterDate, ckptFilterStage);
                  }}
                  options={ckptGroups.map((g) => ({ label: `群: ${g}`, value: g }))}
                />
              </Col>

              <Col xs={24} sm={6} md={5}>
                <Input
                  allowClear
                  placeholder="归属日期 (如 2026-09-10)"
                  value={ckptFilterDate}
                  onChange={(e) => vm.setCkptFilterDate(e.target.value.trim() || undefined)}
                  onPressEnter={() =>
                    vm.loadCheckpoints(1, checkpointsPageSize, ckptFilterGroup, ckptFilterDate, ckptFilterStage)
                  }
                />
              </Col>

              <Col xs={24} sm={6} md={5}>
                <Select
                  style={{ width: "100%" }}
                  allowClear
                  placeholder="按流水线阶段筛选"
                  value={ckptFilterStage}
                  onChange={(val) => {
                    vm.setCkptFilterStage(val);
                    vm.loadCheckpoints(1, checkpointsPageSize, ckptFilterGroup, ckptFilterDate, val);
                  }}
                  options={[
                    { label: "全部阶段", value: "" },
                    { label: "拉取聊天记录 (FETCH_MESSAGES)", value: "FETCH_MESSAGES" },
                    { label: "消息清洗过滤 (CLEAN_MESSAGES)", value: "CLEAN_MESSAGES" },
                    { label: "基础统计分析 (STATS_ANALYSIS)", value: "STATS_ANALYSIS" },
                    { label: "大模型话题与画像分析 (LLM_ANALYSIS)", value: "LLM_ANALYSIS" },
                    { label: "历史记录持久化 (SAVE_SUMMARY)", value: "SAVE_SUMMARY" },
                    { label: "报告长图渲染 (RENDER_REPORT)", value: "RENDER_REPORT" },
                    { label: "群聊消息投递 (DISPATCH_REPORT)", value: "DISPATCH_REPORT" },
                  ]}
                />
              </Col>

              <Col xs={24} sm={6} md={6}>
                <Space size={8}>
                  <Button
                    type="primary"
                    size="small"
                    onClick={() =>
                      vm.loadCheckpoints(1, checkpointsPageSize, ckptFilterGroup, ckptFilterDate, ckptFilterStage)
                    }
                    loading={loadingCheckpoints}
                  >
                    查询
                  </Button>
                  <Button
                    size="small"
                    icon={<ReloadOutlined spin={loadingCheckpoints} />}
                    onClick={() => {
                      vm.refreshCheckpointGroups();
                      vm.loadCheckpoints();
                    }}
                  >
                    刷新
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* Checkpoint 列表 */}
          <Card
            size="small"
            title={
              <Space size={8}>
                <SaveOutlined style={{ color: "#2563eb" }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  阶段产物快照 (Checkpoint) 列表
                </span>
                <Tag color="blue" style={{ fontSize: 11 }}>
                  共 {checkpointsTotal} 条记录
                </Tag>
              </Space>
            }
          >
            <Table<CheckpointItem>
              rowKey={(r) => `${r.group_id}_${r.date_str}_${r.stage_name}`}
              columns={ckptColumns}
              dataSource={checkpoints}
              loading={loadingCheckpoints}
              size="small"
              pagination={{
                current: checkpointsPage,
                pageSize: checkpointsPageSize,
                total: checkpointsTotal,
                showSizeChanger: true,
                showQuickJumper: true,
                pageSizeOptions: ["10", "20", "50", "100"],
                showTotal: (total) => `共 ${total} 条快照`,
                onChange: (page, pageSize) => {
                  vm.loadCheckpoints(page, pageSize, ckptFilterGroup, ckptFilterDate, ckptFilterStage);
                },
              }}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无阶段快照记录（任务成功完成或未开启 Checkpoint）"
                  />
                ),
              }}
            />
          </Card>
        </Space>
      )}

      {/* 底部说明 */}
      <Alert
        message="存储健康与观测说明"
        description={
          <div style={{ fontSize: 12, lineHeight: "1.6" }}>
            <strong>增量分析批次</strong>：记录了各群聊多次增量扫描所生成的话题、金句与发言统计中间态，日报生成完毕后将自动聚合；如发现某时段分析不符合预期，可精准剔除单个批次或重置游标重新扫描。
            <br />
            <strong>阶段产物快照 (Checkpoints)</strong>：流水线各阶段的产物持久化快照，用于任务中断后的断点续跑以及零 Token 主题报告重绘。
          </div>
        }
        type="info"
        showIcon
        style={{ fontSize: 12 }}
      />

      {/* 单批次详情 Modal */}
      <Modal
        title={
          <Space>
            <ThunderboltOutlined style={{ color: "#1677ff" }} />
            <span>
              增量批次详情: {selectedBatchDetail?.batch_id || ""}
            </span>
          </Space>
        }
        open={batchDetailModalOpen}
        onCancel={vm.handleCloseBatchDetail}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() => handleCopyJson(selectedBatchDetail)}
          >
            复制 JSON
          </Button>,
          <Button key="close" type="primary" onClick={vm.handleCloseBatchDetail}>
            关闭
          </Button>,
        ]}
        width={750}
      >
        {loadingBatchDetail ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <Text type="secondary">加载批次明细数据中...</Text>
          </div>
        ) : selectedBatchDetail ? (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Row gutter={[8, 8]}>
              <Col span={8}>
                <Text type="secondary">群号: </Text>
                <Text strong>{selectedBatchDetail.group_id}</Text>
              </Col>
              <Col span={8}>
                <Text type="secondary">生成时间: </Text>
                <Text>{formatTimestamp(selectedBatchDetail.timestamp)}</Text>
              </Col>
              <Col span={8}>
                <Text type="secondary">消息量: </Text>
                <Text strong>{selectedBatchDetail.messages_count} 条 ({(selectedBatchDetail.characters_count || 0).toLocaleString()} 字)</Text>
              </Col>
            </Row>

            {selectedBatchDetail.chat_quality_review && (
              <Card size="small" title="聊天质量与氛围评价">
                <Paragraph style={{ margin: 0, fontSize: 12 }}>
                  {selectedBatchDetail.chat_quality_review}
                </Paragraph>
              </Card>
            )}

            <div>
              <Text strong style={{ fontSize: 12, marginBottom: 4, display: "block" }}>
                底层完整批次数据 (JSON):
              </Text>
              <pre
                style={{
                  fontSize: 11,
                  fontFamily:
                    "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
                  background: token.colorFillAlter,
                  color: token.colorText,
                  border: `1px solid ${token.colorBorderSecondary}`,
                  padding: "8px 10px",
                  borderRadius: 4,
                  maxHeight: 280,
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  margin: 0,
                }}
              >
                {JSON.stringify(selectedBatchDetail, null, 2)}
              </pre>
            </div>
          </Space>
        ) : null}
      </Modal>

      {/* 快照 JSON 详情 Modal */}
      <Modal
        title={
          <Space>
            <SaveOutlined style={{ color: "#2563eb" }} />
            <span>
              阶段快照产物 JSON: {formatStageName(selectedCkptDetail?.stage_name)} ({selectedCkptDetail?.stage_name || "-"})
            </span>
          </Space>
        }
        open={ckptDetailModalOpen}
        onCancel={vm.handleCloseCkptDetail}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() => handleCopyJson(selectedCkptDetail?.data)}
          >
            复制产物数据
          </Button>,
          <Button key="close" type="primary" onClick={vm.handleCloseCkptDetail}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {loadingCkptDetail ? (
          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <Text type="secondary">加载快照产物数据中...</Text>
          </div>
        ) : selectedCkptDetail ? (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Row gutter={[8, 8]}>
              <Col span={8}>
                <Text type="secondary">群号: </Text>
                <Text strong>{selectedCkptDetail.group_id || "-"}</Text>
              </Col>
              <Col span={8}>
                <Text type="secondary">日期: </Text>
                <Tag color="cyan">{selectedCkptDetail.date_str || "-"}</Tag>
              </Col>
              <Col span={8}>
                <Text type="secondary">阶段: </Text>
                <Tag color={getStageMeta(selectedCkptDetail.stage_name || "").color}>
                  {formatStageName(selectedCkptDetail.stage_name)} ({selectedCkptDetail.stage_name || "-"})
                </Tag>
              </Col>
            </Row>

            <div>
              <Text strong style={{ fontSize: 12, marginBottom: 4, display: "block" }}>
                阶段产物数据 (JSON):
              </Text>
              <pre
                style={{
                  fontSize: 11,
                  fontFamily:
                    "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
                  background: token.colorFillAlter,
                  color: token.colorText,
                  border: `1px solid ${token.colorBorderSecondary}`,
                  padding: "8px 10px",
                  borderRadius: 4,
                  maxHeight: 340,
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  margin: 0,
                }}
              >
                {JSON.stringify(selectedCkptDetail.data, null, 2)}
              </pre>
            </div>
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
};
