import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Space,
  Spin,
  Table,
  Typography,
} from "antd";
import { HistoryOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ConfigBackupInfo } from "../../../entities/plugin-data/model/configBackup";
import { formatBytes } from "../../../shared/lib/formatters";
import { useConfigBackups } from "../model/useConfigBackups";
import { JsonBackupTree } from "./JsonBackupTree";

const kindLabels = {
  upgrade: "升级配置备份",
  comic_migration: "漫画配置迁移备份",
  other: "其他 JSON 备份",
};

export function ConfigBackupsViewer() {
  const vm = useConfigBackups();
  return (
    <>
      <Button
        size="small"
        type="link"
        icon={<HistoryOutlined />}
        onClick={vm.load}
      >
        查看备份
      </Button>
      <Modal
        title="配置自动备份"
        open={vm.open}
        onCancel={vm.close}
        width={1080}
        footer={<Button onClick={vm.close}>关闭</Button>}
        destroyOnHidden
      >
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Space wrap>
            <Typography.Text type="secondary">
              选择一份备份，展开查看当时保存的原始键值。没有记录的版本和时间会标为“未记录”。
            </Typography.Text>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={vm.load}
              loading={vm.loading}
            >
              刷新列表
            </Button>
          </Space>
          {vm.error && <Alert type="error" showIcon message={vm.error} />}
          <Table<ConfigBackupInfo>
            size="small"
            rowKey="filename"
            loading={vm.loading}
            dataSource={vm.items}
            pagination={{ pageSize: 5, showSizeChanger: false }}
            scroll={{ x: 800 }}
            locale={{ emptyText: "暂无配置备份" }}
            columns={[
              {
                title: "文件名",
                dataIndex: "filename",
                render: (value: string) => (
                  <Typography.Text style={{ overflowWrap: "anywhere" }}>
                    {value}
                  </Typography.Text>
                ),
              },
              {
                title: "类型",
                dataIndex: "kind",
                width: 138,
                render: (kind: ConfigBackupInfo["kind"]) => kindLabels[kind],
              },
              {
                title: "插件版本",
                dataIndex: "plugin_version",
                width: 100,
                render: (value: string | null) => value || "未记录",
              },
              {
                title: "备份时间",
                dataIndex: "saved_at",
                width: 170,
                render: (value: string | null) =>
                  value ? value.replace("T", " ") : "未记录",
              },
              {
                title: "大小",
                dataIndex: "size_bytes",
                width: 85,
                render: formatBytes,
              },
              {
                title: "操作",
                width: 90,
                render: (_: unknown, item) =>
                  item.error ? (
                    <Typography.Text type="danger" title={item.error}>
                      无法读取
                    </Typography.Text>
                  ) : (
                    <Button
                      size="small"
                      type="link"
                      onClick={() => vm.select(item.filename)}
                    >
                      查看
                    </Button>
                  ),
              },
            ]}
          />
          {vm.detailLoading && (
            <Spin tip="正在读取备份">
              <div style={{ height: 80 }} />
            </Spin>
          )}
          {vm.detailError && (
            <Alert type="error" showIcon message={vm.detailError} />
          )}
          {vm.detail && (
            <Card
              size="small"
              title={
                <Typography.Text style={{ overflowWrap: "anywhere" }}>
                  {vm.detail.backup.filename}
                </Typography.Text>
              }
            >
              <div style={{ maxHeight: "50vh", overflow: "auto" }}>
                <JsonBackupTree
                  key={vm.detail.backup.filename}
                  label="原始 JSON"
                  value={vm.detail.content}
                />
              </div>
            </Card>
          )}
          {!vm.detail &&
            !vm.detailLoading &&
            !vm.detailError &&
            vm.items.length > 0 && (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="点击“查看”展开一份备份"
              />
            )}
        </Space>
      </Modal>
    </>
  );
}
