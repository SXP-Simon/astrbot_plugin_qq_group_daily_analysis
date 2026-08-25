import React from "react";
import { Table, Tag, Empty, Button, Tooltip } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import { ActiveTask } from "../../entities/task/model/types";
import { TaskStageBadge } from "../../entities/task/ui/TaskStageBadge";
import { CancelTaskButton } from "../../features/cancel-task/ui/CancelTaskButton";
import { SectionHeader } from "../../shared/ui/SectionHeader";

interface ActiveTaskBoardProps {
  tasks: ActiveTask[];
  onCancelTask: (taskId: string) => Promise<void> | void;
  onViewTrace: (traceId: string) => void;
  onOpenTrigger: () => void;
}

export const ActiveTaskBoard: React.FC<ActiveTaskBoardProps> = ({
  tasks,
  onCancelTask,
  onViewTrace,
  onOpenTrigger,
}) => {
  const columns = [
    {
      title: "任务 / Trace ID",
      dataIndex: "task_id",
      key: "task_id",
      width: 170,
      render: (id: string) => (
        <a
          className="font-mono text-xs font-semibold"
          onClick={() => onViewTrace(id)}
        >
          {id}
        </a>
      ),
    },
    {
      title: "群组",
      dataIndex: "group_id",
      key: "group_id",
      render: (gid: string, r: ActiveTask) => (
        <Tooltip title={`群号: ${gid}`}>
          <span className="font-mono text-xs">
            {r.group_name || "未知群"} ({gid})
          </span>
        </Tooltip>
      ),
    },
    {
      title: "平台",
      dataIndex: "platform",
      key: "platform",
      width: 85,
      render: (p: string) => <Tag>{p || "qq"}</Tag>,
    },
    {
      title: "触发源",
      dataIndex: "trigger_type",
      key: "trigger_type",
      width: 90,
      render: (t: string) => <Tag>{t}</Tag>,
    },
    {
      title: "当前执行阶段",
      dataIndex: "current_stage",
      key: "current_stage",
      render: (stage: string) => <TaskStageBadge stage={stage} />,
    },
    {
      title: "运行时长",
      dataIndex: "duration_s",
      key: "duration_s",
      width: 95,
      render: (d: number) => (
        <span className="font-mono text-xs font-semibold" style={{ color: "#fa8c16" }}>
          {d}s
        </span>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 130,
      render: (_value: unknown, r: ActiveTask) => (
        <div style={{ display: "flex", gap: 4 }}>
          <Button
            size="small"
            type="link"
            icon={<EyeOutlined />}
            onClick={() => onViewTrace(r.task_id)}
          >
            追踪
          </Button>
          <CancelTaskButton taskId={r.task_id} onCancel={onCancelTask} />
        </div>
      ),
    },
  ];

  return (
    <div>
      <SectionHeader
        title="正在执行中的任务 (Active Tasks)"
        badge={
          <Tag color={tasks.length > 0 ? "processing" : "default"} className="font-mono text-xs">
            {tasks.length} 运行中
          </Tag>
        }
      />

      {tasks.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无正在执行的后台分析任务"
          style={{ margin: "24px 0" }}
        >
          <Button size="small" type="dashed" onClick={onOpenTrigger}>
            手动触发一次分析
          </Button>
        </Empty>
      ) : (
        <Table
          size="small"
          columns={columns}
          dataSource={tasks}
          rowKey="task_id"
          pagination={false}
        />
      )}
    </div>
  );
};
