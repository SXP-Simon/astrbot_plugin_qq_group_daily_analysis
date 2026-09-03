import React from "react";
import { Space, Input, Select, DatePicker, Button } from "antd";
import { SearchOutlined, ReloadOutlined } from "@ant-design/icons";
import { GroupItem } from "../../../entities/group/model/types";

const { RangePicker } = DatePicker;

interface TraceFilterBarProps {
  search: string;
  selectedGroup?: string;
  statusFilter?: string;
  triggerTypeFilter?: string;
  groups: GroupItem[];
  loading: boolean;
  onSearchChange: (val: string) => void;
  onGroupChange: (val?: string) => void;
  onStatusChange: (val?: string) => void;
  onTriggerTypeChange?: (val?: string) => void;
  onDateRangeChange: (dates: [number, number] | null) => void;
  onRefresh: () => void;
}

export const TraceFilterBar: React.FC<TraceFilterBarProps> = ({
  search,
  selectedGroup,
  statusFilter,
  triggerTypeFilter,
  groups,
  loading,
  onSearchChange,
  onGroupChange,
  onStatusChange,
  onTriggerTypeChange,
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
          style={{ width: 190 }}
          allowClear
        />

        <Select
          size="small"
          placeholder="选择群聊"
          value={selectedGroup}
          onChange={onGroupChange}
          style={{ width: 160 }}
          allowClear
          showSearch
          optionFilterProp="label"
          options={groups.map((g) => ({
            label: `${g.group_name || "未知群"} (${g.group_id})`,
            value: g.group_id,
          }))}
        />

        {onTriggerTypeChange && (
          <Select
            size="small"
            placeholder="触发方式"
            value={triggerTypeFilter}
            onChange={onTriggerTypeChange}
            style={{ width: 115 }}
            allowClear
            options={[
              { label: "全部方式", value: undefined },
              { label: "增量日报", value: "incremental_report" },
              { label: "增量分析", value: "incremental" },
              { label: "定时分析", value: "auto" },
              { label: "手动触发", value: "manual" },
              { label: "控制台触发", value: "web_manual" },
              { label: "群漫画生成", value: "comic_manual" },
              { label: "断点续跑", value: "resume_analysis" },
              { label: "主题重绘", value: "rerender_report" },
            ]}
          />
        )}

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
            { label: "部分成功 / 警告", value: "warning" },
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
