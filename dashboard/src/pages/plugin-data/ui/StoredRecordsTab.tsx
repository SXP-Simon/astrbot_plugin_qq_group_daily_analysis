import { LoadingSkeleton, LoadingState } from "../../../shared/ui/loading-state";
import { useEffect, useState } from "react";
import { IconEye, IconRefresh, IconSearch, IconUpload, IconX } from "@tabler/icons-react";
import type { RecordLocator } from "../../../entities/plugin-data/api/managedRecordsApi";
import { formatBytes } from "../../../shared/lib/formatters";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { Pagination } from "../../../shared/ui/pagination";
import { useStoredRecords } from "../model/useStoredRecords";
import { useRecordSelection, recordKey } from "../model/useRecordSelection";
import { RecordSelectionActions } from "./RecordSelectionActions";
import { ManagedRecordDialog } from "./ManagedRecordDialog";

export function StoredRecordsTab({ onlyKind }: { onlyKind?: "avatar" | "history" }) {
  const vm = useStoredRecords(onlyKind || "history");
  const { kind, setKind, search, setSearch, page, setPage, items, total, loading, error, refresh } =
    vm;
  const [draft, setDraft] = useState("");
  const [selected, setSelected] = useState<RecordLocator | null>(null);
  const [importing, setImporting] = useState(false);
  const selection = useRecordSelection(
    items.map((item) => item.locator),
    () => void refresh(),
  );
  const clear = selection.clear;
  useEffect(() => {
    clear();
    setSelected(null);
    setImporting(false);
  }, [kind, search, clear]);
  useEffect(() => {
    setDraft(search);
  }, [search]);
  const keys = items.map((item) => recordKey(item.locator));
  return (
    <section
      className="grid min-w-0 gap-4"
      aria-label={kind === "avatar" ? "头像缓存条目" : "分析历史存档"}
    >
      {!onlyKind && (
        <fieldset disabled={selection.busy} className="m-0 flex flex-wrap gap-2 border-0 p-0">
          <legend className="sr-only">记录类型</legend>
          {(
            [
              { value: "history", label: "分析历史" },
              { value: "avatar", label: "头像缓存" },
            ] as const
          ).map((option) => (
            <label
              key={option.value}
              className={`flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm ${kind === option.value ? "bg-primary/15 text-foreground" : "bg-muted/40 text-muted-foreground"}`}
            >
              <input
                type="radio"
                name={onlyKind || "stored-record-kind"}
                value={option.value}
                checked={kind === option.value}
                className="size-4 accent-primary"
                onChange={() => setKind(option.value)}
              />
              {option.label}
            </label>
          ))}
        </fieldset>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <form
          className="flex min-w-0 flex-1 flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (selection.busy) return;
            if (draft.trim() === search) void refresh();
            else setSearch(draft);
          }}
        >
          <label className="grid min-w-0 grow gap-1.5 text-sm sm:max-w-md">
            搜索记录
            <Input
              type="search"
              aria-label="搜索业务记录"
              placeholder="群号、日期或缓存键"
              value={draft}
              disabled={selection.busy}
              onChange={(event) => setDraft(event.target.value)}
            />
          </label>
          <Button type="submit" variant="outline" disabled={selection.busy}>
            <IconSearch aria-hidden="true" />
            搜索
          </Button>
          {(draft || search) && (
            <Button
              variant="ghost"
              disabled={selection.busy}
              onClick={() => {
                setDraft("");
                setSearch("");
              }}
            >
              <IconX aria-hidden="true" />
              清空搜索
            </Button>
          )}
        </form>
        <Button
          variant="outline"
          disabled={loading || selection.busy}
          onClick={() => void refresh()}
        >
          <IconRefresh aria-hidden="true" />
          刷新记录
        </Button>
        {kind === "history" && (
          <Button disabled={selection.busy} onClick={() => setImporting(true)}>
            <IconUpload aria-hidden="true" />
            导入历史记录
          </Button>
        )}
      </div>
      <p className="m-0 text-sm text-muted-foreground">
        {kind === "history"
          ? "保留完整分析存档，包含摘要和重绘所需数据；每日索引不重复列出。"
          : "按平台缓存键管理头像，打开详情时才读取图片。磁盘占用可在存储概览查看。"}
      </p>
      {error && (
        <p role="alert" className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}
      <RecordSelectionActions
        key={`${kind}:${search}`}
        vm={selection}
        label={kind === "history" ? "分析存档" : "头像缓存"}
      />
      {loading && (
        <LoadingState className="m-0 text-sm text-muted-foreground">正在读取记录…</LoadingState>
      )}
      <div
        role="region"
        aria-label="存档与头像列表"
        tabIndex={0}
        className="overflow-x-auto rounded-xl border border-border focus-visible:outline-2 focus-visible:outline-ring"
        aria-busy={loading}
      >
        <table className="ui-data-table w-full min-w-[600px] text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="w-10 p-3 font-medium">
                <input
                  type="checkbox"
                  aria-label="选择本页记录"
                  className="size-4 accent-primary"
                  disabled={selection.busy || loading || !keys.length}
                  checked={keys.length > 0 && keys.every((key) => selection.keys.includes(key))}
                  onChange={(event) =>
                    selection.select(
                      event.target.checked
                        ? [...new Set([...selection.keys, ...keys])]
                        : selection.keys.filter((key) => !keys.includes(key)),
                    )
                  }
                />
              </th>
              <th className="p-3 font-medium">记录标识</th>
              {kind === "history" && <th className="p-3 font-medium">群聊</th>}
              <th className="p-3 font-medium">数据大小</th>
              <th className="p-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && !items.length && (
              <tr aria-hidden="true">
                <td colSpan={kind === "history" ? 5 : 4} className="p-4">
                  <LoadingSkeleton />
                </td>
              </tr>
            )}
            {items.map((item) => {
              const key = recordKey(item.locator);
              return (
                <tr
                  key={key}
                  aria-selected={selection.keys.includes(key)}
                  className="border-t border-border"
                >
                  <td className="p-3">
                    <input
                      type="checkbox"
                      aria-label={`选择记录 ${item.name}`}
                      className="size-4 accent-primary"
                      checked={selection.keys.includes(key)}
                      disabled={selection.busy || loading}
                      onChange={(event) =>
                        selection.select(
                          event.target.checked
                            ? [...selection.keys, key]
                            : selection.keys.filter((value) => value !== key),
                        )
                      }
                    />
                  </td>
                  <td className="max-w-lg break-all p-3 font-mono text-xs">{item.name}</td>
                  {kind === "history" && (
                    <td className="max-w-40 break-all p-3 font-mono text-xs">
                      {item.locator.group_id || "未记录"}
                    </td>
                  )}
                  <td className="whitespace-nowrap p-3 text-muted-foreground">
                    {kind === "avatar" ? "按需加载" : formatBytes(item.size_bytes)}
                  </td>
                  <td className="p-3">
                    <Button
                      variant="tonal"
                      size="sm"
                      disabled={selection.busy || loading}
                      onClick={() => setSelected(item.locator)}
                    >
                      <IconEye aria-hidden="true" />
                      {kind === "avatar" ? "预览与管理" : "查看与管理"}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && !items.length && !error && (
          <p role="status" className="p-6 text-center text-sm text-muted-foreground">
            {search ? "没有匹配的记录，可清空搜索后重试。" : "暂无记录。"}
          </p>
        )}
      </div>
      {(total > 0 || (!loading && !error)) && (
        <Pagination
          page={page}
          pageSize={20}
          pageSizes={[20]}
          total={total}
          loading={loading}
          disabled={selection.busy}
          onChange={setPage}
        />
      )}
      <ManagedRecordDialog
        locator={selected}
        importKind={importing ? "history" : undefined}
        onClose={() => {
          setSelected(null);
          setImporting(false);
        }}
        onChanged={() => void refresh()}
      />
    </section>
  );
}
