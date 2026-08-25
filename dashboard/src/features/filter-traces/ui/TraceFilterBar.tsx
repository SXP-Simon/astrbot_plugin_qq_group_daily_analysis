import React from "react";
import { Space, Input, Select, DatePicker, Button } from "antd";
import { SearchOutlined, ReloadOutlined } from "@ant-design/icons";
import { GroupItem } from "../../../entities/group/model/types";

const { RangePicker } = DatePicker;

interface TraceFilterBarProps {
  search: string;
  selectedGroup?: string;
  statusFilter?: string;
  groups: GroupItem[];
  loading: boolean;
  onSearchChange: (val: string) => void;
  onGroupChange: (val?: string) => void;
  onStatusChange: (val?: string) => void;
  onDateRangeChange: (dates: [number, number] | null) => void;
  onRefresh: () => void;
}

export const TraceFilterBar: React.FC<TraceFilterBarProps> = ({
  search,
  selectedGroup,
  statusFilter,
  groups,
  loading,
  onSearchChange,
  onGroupChange,
  onStatusChange,
  onDateRangeChange,
  onRefresh,
}) => {
  return (
    <Space
      size="small"
      style={{
        marginBottom: 12,
        width: "100%",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 8,
      }}
    >
      <Space wrap size="small">
        <Input
          size="small"
          placeholder="搜索 任务编号 / 群号 / 群名"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />

        <Select
          size="small"
          placeholder="选择群聊"
          value={selectedGroup}
          onChange={onGroupChange}
          style={{ width: 170 }}
          allowClear
          showSearch
          optionFilterProp="label"
          options={groups.map((g) => ({
            label: `${g.group_name || "未知群"} (${g.group_id})`,
            value: g.group_id,
          }))}
        />

        <Select
          size="small"
          placeholder="执行状态"
          value={statusFilter}
          onChange={onStatusChange}
          style={{ width: 115 }}
          allowClear
          options={[
            { label: "全部状态", value: undefined },
            { label: "执行成功", value: "succeeded" },
            { label: "执行失败", value: "failed" },
            { label: "正在运行", value: "running" },
            { label: "已手动中止", value: "aborted" },
          ]}
        />

        <RangePicker
          size="small"
          style={{ width: 230 }}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              const start = dates[0].startOf("day").unix();
              const end = dates[1].endOf("day").unix();
              onDateRangeChange([start, end]);
            } else {
              onDateRangeChange(null);
            }
          }}
        />
      </Space>

      <Button
        size="small"
        icon={<ReloadOutlined spin={loading} />}
        onClick={onRefresh}
      >
        刷新
      </Button>
    </Space>
  );
};
