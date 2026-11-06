import { useEffect, useId, useRef, useState } from "react";
import { IconRefresh, IconX } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";
import { SearchSelect } from "../../../shared/ui/search-select";
import type { GroupItem } from "../../../entities/group/model/types";

interface TraceFilterBarProps {
  search: string;
  selectedGroup?: string;
  statusFilter?: string;
  triggerTypeFilter?: string;
  dateRange?: [number, number] | null;
  groups: GroupItem[];
  loading: boolean;
  onSearchChange: (value: string) => void;
  onGroupChange: (value?: string) => void;
  onStatusChange: (value?: string) => void;
  onTriggerTypeChange?: (value?: string) => void;
  onDateRangeChange: (dates: [number, number] | null) => void;
  onReset?: () => void;
  onRefresh: () => void;
}

export function TraceFilterBar(props: TraceFilterBarProps) {
  const [dates, setDates] = useState({ start: "", end: "" });
  const [dateError, setDateError] = useState("");
  const dateErrorId = useId();
  const emittedRange = useRef<[number, number] | null | undefined>(undefined);
  useEffect(() => {
    // 自己发出的筛选更新保留未填写完整的日期，外部重置才同步输入框。
    if (props.dateRange === emittedRange.current) return;
    const values = props.dateRange?.map((timestamp) => {
      const date = new Date(timestamp * 1000);
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    });
    setDates({ start: values?.[0] ?? "", end: values?.[1] ?? "" });
    setDateError("");
  }, [props.dateRange]);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <label className="grid gap-1 text-sm text-muted-foreground">
          搜索
          <Input
            type="search"
            placeholder="任务编号 / 群号 / 群名"
            value={props.search}
            onChange={(event) => props.onSearchChange(event.target.value)}
          />
        </label>
        <div className="grid gap-1 text-sm text-muted-foreground">
          <span>群聊</span>
          <SearchSelect
            label="选择群聊"
            value={props.selectedGroup ?? ""}
            onChange={(value) => props.onGroupChange(value || undefined)}
            options={[
              { value: "", label: "全部群聊" },
              ...props.groups.map((group) => ({
                value: group.group_id,
                label: `${group.group_name || "未知群"}（${group.group_id}）`,
              })),
            ]}
          />
        </div>
        {props.onTriggerTypeChange && (
          <label className="grid gap-1 text-sm text-muted-foreground">
            触发方式
            <NativeSelect
              value={props.triggerTypeFilter ?? ""}
              onChange={(event) => props.onTriggerTypeChange?.(event.target.value || undefined)}
            >
              <option value="">全部方式</option>
              <option value="incremental_report">增量日报</option>
              <option value="incremental">增量分析</option>
              <option value="auto">定时分析</option>
              <option value="manual">手动触发</option>
              <option value="web_manual">控制台触发</option>
              <option value="comic_manual">群漫画生成</option>
              <option value="resume_analysis">断点续跑</option>
              <option value="rerender_report">主题重绘</option>
            </NativeSelect>
          </label>
        )}
        <label className="grid gap-1 text-sm text-muted-foreground">
          执行状态
          <NativeSelect
            value={props.statusFilter ?? ""}
            onChange={(event) => props.onStatusChange(event.target.value || undefined)}
          >
            <option value="">全部状态</option>
            <option value="succeeded">执行成功</option>
            <option value="warning">部分成功 / 警告</option>
            <option value="failed">执行失败</option>
            <option value="skipped">已跳过</option>
            <option value="running">正在运行</option>
            <option value="aborted">已中止</option>
          </NativeSelect>
        </label>
      </div>
      <div className="grid grid-cols-2 items-end gap-3 sm:flex sm:flex-wrap">
        {(["start", "end"] as const).map((key) => (
          <label key={key} className="grid min-w-0 gap-1 text-sm text-muted-foreground sm:w-44">
            {key === "start" ? "开始日期" : "结束日期"}
            <Input
              type="date"
              value={dates[key]}
              aria-invalid={Boolean(dateError)}
              aria-describedby={dateError ? dateErrorId : undefined}
              onChange={(event) => {
                const next = { ...dates, [key]: event.target.value };
                setDates(next);
                if (next.start && next.end) {
                  const start = new Date(`${next.start}T00:00:00`).getTime();
                  const end = new Date(`${next.end}T23:59:59.999`).getTime();
                  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
                    setDateError("结束日期不能早于开始日期。");
                    return;
                  }
                  setDateError("");
                  const range: [number, number] = [
                    Math.floor(start / 1000),
                    Math.floor(end / 1000),
                  ];
                  emittedRange.current = range;
                  props.onDateRangeChange(range);
                } else {
                  setDateError("");
                  emittedRange.current = null;
                  props.onDateRangeChange(null);
                }
              }}
            />
          </label>
        ))}
        <Button
          variant="ghost"
          onClick={() => {
            setDates({ start: "", end: "" });
            setDateError("");
            if (props.onReset) props.onReset();
            else {
              props.onSearchChange("");
              props.onGroupChange(undefined);
              props.onStatusChange(undefined);
              props.onTriggerTypeChange?.(undefined);
              props.onDateRangeChange(null);
            }
          }}
        >
          <IconX aria-hidden="true" />
          清空筛选
        </Button>
        <Button
          variant="outline"
          className="sm:ml-auto"
          disabled={props.loading}
          onClick={props.onRefresh}
        >
          <IconRefresh aria-hidden="true" className={props.loading ? "animate-spin" : undefined} />
          刷新
        </Button>
      </div>
      {dateError && (
        <p id={dateErrorId} role="alert" className="m-0 text-sm text-destructive">
          {dateError}
        </p>
      )}
    </div>
  );
}
