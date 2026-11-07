import { useEffect, useId, useRef, useState } from "react";
import { IconRefresh, IconX } from "@tabler/icons-react";
import { Input } from "../../../shared/ui/input";
import { Button } from "../../../shared/ui/button";
import { GroupFilters } from "../../../entities/group/ui/GroupFilters";
import type { GroupItem } from "../../../entities/group/model/types";

interface ReportFilterBarProps {
  search: string;
  selectedGroup?: string;
  selectedPlatform?: string;
  onPlatformChange?: (value?: string) => void;
  dateRange: [number, number] | null;
  groups: GroupItem[];
  loading: boolean;
  onSearchChange: (value: string) => void;
  onGroupChange: (value?: string, platform?: string) => void;
  onDateRangeChange: (dates: [number, number] | null) => void;
  onReset: () => void;
  onRefresh: () => void;
}

export function ReportFilterBar(props: ReportFilterBarProps) {
  const [dates, setDates] = useState({ start: "", end: "" });
  const [error, setError] = useState("");
  const id = useId();
  const emitted = useRef<[number, number] | null | undefined>(undefined);
  useEffect(() => {
    if (props.dateRange === emitted.current) return;
    const values = props.dateRange?.map((timestamp) => {
      const date = new Date(timestamp * 1000);
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    });
    setDates({ start: values?.[0] ?? "", end: values?.[1] ?? "" });
    setError("");
  }, [props.dateRange]);
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_2fr]">
        <label className="grid gap-1 text-sm text-muted-foreground">
          搜索报告
          <Input
            type="search"
            placeholder="文件名 / 群号 / 任务编号"
            value={props.search}
            onChange={(event) => props.onSearchChange(event.target.value)}
          />
        </label>
        <GroupFilters
          groups={props.groups}
          selectedGroup={props.selectedGroup}
          selectedPlatform={props.selectedPlatform}
          onPlatformChange={props.onPlatformChange}
          onGroupChange={props.onGroupChange}
        />
      </div>
      <div className="grid grid-cols-2 items-end gap-3 sm:flex sm:flex-wrap">
        {(["start", "end"] as const).map((key) => (
          <label key={key} className="grid min-w-0 gap-1 text-sm text-muted-foreground sm:w-44">
            {key === "start" ? "开始日期" : "结束日期"}
            <Input
              type="date"
              value={dates[key]}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? id : undefined}
              onChange={(event) => {
                const next = { ...dates, [key]: event.target.value };
                setDates(next);
                if (next.start && next.end) {
                  const start = new Date(`${next.start}T00:00:00`).getTime();
                  const end = new Date(`${next.end}T23:59:59.999`).getTime();
                  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
                    setError("结束日期不能早于开始日期。");
                    return;
                  }
                  setError("");
                  const range: [number, number] = [Math.floor(start / 1000), end / 1000];
                  emitted.current = range;
                  props.onDateRangeChange(range);
                } else {
                  setError("");
                  emitted.current = null;
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
            setError("");
            props.onReset();
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
      {error && (
        <p id={id} role="alert" className="m-0 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
