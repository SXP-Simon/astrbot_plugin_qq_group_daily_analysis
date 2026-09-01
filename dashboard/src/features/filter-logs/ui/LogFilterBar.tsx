import React from "react";
import { Space, Input, Select, Switch, Button, Tooltip, Tag } from "antd";
import {
  SearchOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CopyOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { AvailableTag, TAG_STYLE_MAP } from "../../../entities/log/model/types";
import { useTheme } from "../../../shared/lib/useTheme";

interface LogFilterBarProps {
  search: string;
  level?: string;
  tag?: string;
  availableTags: AvailableTag[];
  autoRefresh: boolean;
  loading: boolean;
  onSearchChange: (val: string) => void;
  onLevelChange: (val?: string) => void;
  onTagChange: (val?: string) => void;
  onAutoRefreshChange: (val: boolean) => void;
  onRefresh: () => void;
  onClear: () => void;
  onCopyAll: () => void;
}

export const LogFilterBar: React.FC<LogFilterBarProps> = ({
  search,
  level,
  tag,
  availableTags,
  autoRefresh,
  loading,
  onSearchChange,
  onLevelChange,
  onTagChange,
  onAutoRefreshChange,
  onRefresh,
  onClear,
  onCopyAll,
}) => {
  const { isDark } = useTheme();

  return (
    <Space
      size="small"
      style={{
        marginBottom: 10,
        width: "100%",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 8,
      }}
    >
      <Space wrap size="small">
        <Input
          size="small"
          placeholder="搜索日志内容 / TraceID / 模块"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{ width: 220 }}
          allowClear
        />

        <Select
          size="small"
          placeholder="日志级别"
          value={level}
          onChange={onLevelChange}
          style={{ width: 120 }}
          allowClear
          options={[
            { label: "全部级别", value: undefined },
            {
              label: (
                <Tag color="processing" style={{ margin: 0, fontSize: 11, padding: "0 4px", lineHeight: "18px" }}>
                  INFO
                </Tag>
              ),
              value: "INFO",
            },
            {
              label: (
                <Tag color="warning" style={{ margin: 0, fontSize: 11, padding: "0 4px", lineHeight: "18px" }}>
                  WARNING
                </Tag>
              ),
              value: "WARNING",
            },
            {
              label: (
                <Tag color="error" style={{ margin: 0, fontSize: 11, padding: "0 4px", lineHeight: "18px" }}>
                  ERROR
                </Tag>
              ),
              value: "ERROR",
            },
            {
              label: (
                <Tag style={{ margin: 0, fontSize: 11, padding: "0 4px", lineHeight: "18px", color: isDark ? "#8c8c8c" : "#595959" }}>
                  DEBUG
                </Tag>
              ),
              value: "DEBUG",
            },
          ]}
        />

        <Select
          size="small"
          placeholder="功能分类"
          value={tag}
          onChange={onTagChange}
          style={{ width: 180 }}
          allowClear
          options={[
            { label: "全部分类", value: undefined },
            ...availableTags.map((t) => {
              const cfg = TAG_STYLE_MAP[t.key] || { label: t.label, color: "default" };
              return {
                label: (
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Tag
                      color={cfg.color}
                      style={{
                        margin: 0,
                        fontSize: 10,
                        padding: "0 4px",
                        lineHeight: "18px",
                        flexShrink: 0,
                      }}
                    >
                      {t.key}
                    </Tag>
                    <span style={{ fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.label}
                    </span>
                  </div>
                ),
                value: t.key,
              };
            }),
          ]}
        />

        <Space size={4}>
          <Switch
            size="small"
            checked={autoRefresh}
            onChange={onAutoRefreshChange}
          />
          <span style={{ fontSize: 12, color: isDark ? "#bfbfbf" : "#595959" }}>
            {autoRefresh ? (
              <span>
                <SyncOutlined spin style={{ color: "#1677ff", marginRight: 4 }} />
                实时自动刷新
              </span>
            ) : (
              "实时自动刷新"
            )}
          </span>
        </Space>
      </Space>

      <Space size="small">
        <Tooltip title="一键复制当前筛选出的日志文本">
          <Button size="small" icon={<CopyOutlined />} onClick={onCopyAll}>
            复制日志
          </Button>
        </Tooltip>

        <Button
          size="small"
          icon={<ReloadOutlined spin={loading} />}
          onClick={onRefresh}
        >
          刷新
        </Button>

        <Button
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={onClear}
        >
          清空
        </Button>
      </Space>
    </Space>
  );
};
