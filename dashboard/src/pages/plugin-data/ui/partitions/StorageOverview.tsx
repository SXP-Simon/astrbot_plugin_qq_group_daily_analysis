import {
  Alert,
  Button,
  Card,
  Col,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { FolderOpenOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ManagedPartition } from "../../../../entities/plugin-data/api/managedFilesApi";
import { partitionPresentation } from "../../../../entities/plugin-data/model/partitionPresentation";
import type { useManagedFiles } from "../../../../features/manage-stored-files/model/useManagedFiles";
import { formatBytes } from "../../../../shared/lib/formatters";

export function StorageOverview({
  vm,
  onSelect,
}: {
  vm: ReturnType<typeof useManagedFiles>;
  onSelect: (partition: ManagedPartition) => void;
}) {
  const { totalBytes, totalFiles, assetBytes } = vm.totals;
  return (
    <>
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="插件文件占用" value={formatBytes(totalBytes)} />
            <Typography.Text type="secondary">共 {totalFiles} 个文件</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="受管理分区" value={vm.partitions.length} />
            <Typography.Text type="secondary">按模块提供对应操作</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="字体与原始素材" value={formatBytes(assetBytes)} />
            <Typography.Text type="secondary">支持按主题补齐与单项维护</Typography.Text>
          </Card>
        </Col>
      </Row>
      {vm.error && (
        <Alert
          type="error"
          showIcon
          message={vm.error}
          action={<Button onClick={() => void vm.refresh()}>重试</Button>}
        />
      )}
      <Card
        size="small"
        title={
          <Space>
            <FolderOpenOutlined />
            存储分区明细与管理
          </Space>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => void vm.refresh()}>
            刷新概览
          </Button>
        }
      >
        <Table<ManagedPartition>
          rowKey="key"
          size="small"
          dataSource={vm.partitions}
          pagination={false}
          scroll={{ x: 860 }}
          columns={[
            {
              title: "数据分区",
              width: 220,
              render: (_, item) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>{item.name}</Typography.Text>
                  <Typography.Text
                    type="secondary"
                    style={{ fontSize: 11, maxWidth: 210 }}
                    ellipsis={{ tooltip: item.directory }}
                  >
                    {item.directory}
                  </Typography.Text>
                </Space>
              ),
            },
            { title: "文件", dataIndex: "count", align: "right", width: 65 },
            {
              title: "占用空间",
              width: 100,
              align: "right",
              render: (_, item) => formatBytes(item.size_bytes),
            },
            {
              title: "占比",
              width: 115,
              render: (_, item) => (
                <Progress
                  size="small"
                  percent={totalBytes ? Math.round((item.size_bytes / totalBytes) * 100) : 0}
                />
              ),
            },
            {
              title: "分区用途与能力",
              render: (_, item) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{item.description}</Typography.Text>
                  <Space size={[0, 4]} wrap>
                    {partitionPresentation[item.key]?.capabilities.map((label) => (
                      <Tag key={label} color="blue">
                        {label}
                      </Tag>
                    ))}
                  </Space>
                </Space>
              ),
            },
            {
              title: "操作",
              fixed: "right",
              width: 85,
              render: (_, item) => (
                <Button
                  type="link"
                  onClick={() => {
                    onSelect(item);
                  }}
                >
                  管理
                </Button>
              ),
            },
          ]}
        />
      </Card>
    </>
  );
}
