import {
  IconCopy,
  IconPlayerPause,
  IconPlayerPlay,
  IconRefresh,
  IconTrash,
} from "@tabler/icons-react";
import type { AvailableTag } from "../../../entities/log/model/types";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";

interface LogFilterBarProps {
  search: string;
  level?: string;
  tag?: string;
  availableTags: AvailableTag[];
  autoRefresh: boolean;
  loading: boolean;
  clearing: boolean;
  onSearchChange: (value: string) => void;
  onLevelChange: (value?: string) => void;
  onTagChange: (value?: string) => void;
  onAutoRefreshChange: (value: boolean) => void;
  onRefresh: () => void;
  onClear: () => void;
  onCopyAll: () => void;
}

export function LogFilterBar(props: LogFilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_220px]">
        <label className="col-span-2 grid gap-1 text-sm text-muted-foreground lg:col-span-1">
          搜索日志
          <Input
            type="search"
            placeholder="内容 / 任务编号 / 模块"
            value={props.search}
            onChange={(event) => props.onSearchChange(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm text-muted-foreground">
          日志级别
          <NativeSelect
            value={props.level ?? ""}
            onChange={(event) => props.onLevelChange(event.target.value || undefined)}
          >
            <option value="">全部级别</option>
            {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid gap-1 text-sm text-muted-foreground">
          功能分类
          <NativeSelect
            value={props.tag ?? ""}
            onChange={(event) => props.onTagChange(event.target.value || undefined)}
          >
            <option value="">全部分类</option>
            {props.availableTags.map((tag) => (
              <option key={tag.key} value={tag.key}>
                {tag.label} · {tag.key}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          aria-pressed={props.autoRefresh}
          onClick={() => props.onAutoRefreshChange(!props.autoRefresh)}
        >
          {props.autoRefresh ? (
            <IconPlayerPause aria-hidden="true" />
          ) : (
            <IconPlayerPlay aria-hidden="true" />
          )}
          {props.autoRefresh ? "暂停更新" : "继续更新"}
        </Button>
        <Button variant="ghost" onClick={props.onCopyAll}>
          <IconCopy aria-hidden="true" />
          复制日志
        </Button>
        <Button
          variant="ghost"
          disabled={props.loading || props.clearing}
          onClick={props.onRefresh}
        >
          <IconRefresh aria-hidden="true" />
          {props.loading ? "刷新中…" : "刷新"}
        </Button>
        <Button
          variant="ghost"
          className="text-destructive sm:ml-auto"
          disabled={props.clearing}
          onClick={props.onClear}
        >
          <IconTrash aria-hidden="true" />
          清空日志
        </Button>
      </div>
    </div>
  );
}
