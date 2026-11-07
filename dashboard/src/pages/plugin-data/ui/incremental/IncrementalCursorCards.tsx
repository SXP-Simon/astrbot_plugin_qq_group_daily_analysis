import { formatTimestamp } from "../../../../shared/lib/formatters";
import type { IncrementalCursorInfo } from "../../../../entities/plugin-data/model/types";

export function IncrementalCursorCards({
  cursor,
  batchCount,
}: {
  cursor: IncrementalCursorInfo;
  batchCount: number;
}) {
  const items = [
    {
      label: "上次分析推进时间",
      value:
        cursor.last_analyzed_timestamp > 0
          ? formatTimestamp(cursor.last_analyzed_timestamp)
          : "尚未分析",
      hint: "下次从这个时间之后继续分析。",
      color: "text-foreground",
    },
    {
      label: "最新包含消息时间",
      value:
        cursor.last_message_timestamp !== null && cursor.last_message_timestamp > 0
          ? formatTimestamp(cursor.last_message_timestamp)
          : "未记录",
      hint: "已保存批次涵盖的最新消息。",
      color: "text-foreground",
    },
    {
      label: "已记录去重消息",
      value: `${cursor.tracked_message_ids_count.toLocaleString()} 条`,
      hint: "用于避免跨批次重复统计。",
      color: "text-info",
    },
    {
      label: "暂存批次",
      value: `${batchCount.toLocaleString()} 个`,
      hint: "等待合并到总结中的分析批次。",
      color: "text-creative",
    },
  ];
  return (
    <dl className="m-0 grid grid-cols-1 gap-4 rounded-xl bg-muted/40 p-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-sm text-muted-foreground">{item.label}</dt>
          <dd className={`m-0 mt-1 break-words text-base tabular-nums ${item.color}`}>
            {item.value}
          </dd>
          <dd className="m-0 mt-1 text-xs text-muted-foreground">{item.hint}</dd>
        </div>
      ))}
    </dl>
  );
}
