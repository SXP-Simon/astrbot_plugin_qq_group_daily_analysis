import React from "react";
import { Card, Table, Empty, Button, Tag } from "antd";
import { ReloadOutlined, FileImageOutlined, FolderOpenOutlined } from "@ant-design/icons";
import { formatTimestamp } from "../../../shared/lib/formatters";
import { useReportsViewModel } from "../model/useReportsViewModel";

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ viewModel }) => {
  const { reports, loading, refresh } = viewModel;

  const columns = [
    {
      title: "报告文件",
      dataIndex: "filename",
      key: "filename",
      render: (fn: string) => (
        <span className="font-mono text-xs font-semibold">
          <FileImageOutlined style={{ marginRight: 6, color: "#1677ff" }} />
          {fn}
        </span>
      ),
    },
    {
      title: "文件大小",
      dataIndex: "size_bytes",
      key: "size_bytes",
      width: 120,
      render: (sz: number) => (
        <span className="font-mono text-xs">
          {(sz / 1024).toFixed(1)} KB
        </span>
      ),
    },
    {
      title: "生成时间",
      dataIndex: "modified_at",
      key: "modified_at",
      width: 180,
      render: (ts: number) => (
        <span className="font-mono text-xs" style={{ color: "#595959" }}>
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: "状态",
      key: "status",
      width: 90,
      render: () => <Tag color="success">已生成</Tag>,
    },
  ];

  return (
    <Card
      size="small"
      title={
        <span>
          <FolderOpenOutlined style={{ marginRight: 6, color: "#1677ff" }} />
          历史生成的日报长图
        </span>
      }
      extra={
        <Button
          size="small"
          icon={<ReloadOutlined spin={loading} />}
          onClick={refresh}
        >
          刷新
        </Button>
      }
    >
      {reports.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无历史图片报告产物"
          style={{ margin: "32px 0" }}
        />
      ) : (
        <Table
          size="small"
          columns={columns}
          dataSource={reports}
          rowKey="filename"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      )}
    </Card>
  );
};
