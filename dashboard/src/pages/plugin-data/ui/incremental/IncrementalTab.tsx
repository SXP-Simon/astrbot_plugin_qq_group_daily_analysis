import { useEffect, useState } from "react";
import { IconEye, IconSettings, IconTrash, IconRefresh } from "@tabler/icons-react";
import { ManagedRecordDialog } from "../ManagedRecordDialog";
import { RecordSelectionActions } from "../RecordSelectionActions";
import { useRecordSelection, recordKey } from "../../model/useRecordSelection";
import type { RecordLocator } from "../../../../entities/plugin-data/api/managedRecordsApi";
import type { IncrementalBatchItem } from "../../../../entities/plugin-data/model/types";
import type { usePluginDataViewModel } from "../../model/usePluginDataViewModel";
import { formatTimestamp, formatTokens } from "../../../../shared/lib/formatters";
import { Button } from "../../../../shared/ui/button";
import { Pagination } from "../../../../shared/ui/pagination";
import { SearchSelect } from "../../../../shared/ui/search-select";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../../../../shared/ui/dialog";
import { IncrementalCursorCards } from "./IncrementalCursorCards";

export function IncrementalTab({ vm }: { vm: ReturnType<typeof usePluginDataViewModel> }) {
  const [managedLocator, setManagedLocator] = useState<RecordLocator | null>(null);
  const [importing, setImporting] = useState(false);
  const [confirmation, setConfirmation] = useState<
    | { kind: "delete"; batch: IncrementalBatchItem; platformId: string }
    | { kind: "reset"; groupId: string; platformId: string }
    | null
  >(null);
  const {
    incrGroups,
    selectedIncrGroup,
    selectedIncrPlatform,
    incrBatches,
    incrCursor,
    loadingIncremental,
  } = vm;
  const selection = useRecordSelection(
    incrBatches.map((item) => ({
      kind: "batch",
      platform_id: selectedIncrPlatform,
      group_id: item.group_id,
      batch_id: item.batch_id,
    })),
    () => {
      void vm.refreshIncrGroups();
      void vm.loadIncrementalData(selectedIncrGroup);
    },
  );
  const clearSelection = selection.clear;
  useEffect(() => {
    clearSelection();
  }, [selectedIncrGroup, selectedIncrPlatform, clearSelection]);
  const busy = selection.busy || vm.incrementalBusy;
  const allKeys = incrBatches.map((item) =>
    recordKey({
      kind: "batch",
      platform_id: selectedIncrPlatform,
      group_id: item.group_id,
      batch_id: item.batch_id,
    }),
  );
  return (
    <div className="grid min-w-0 gap-5">
      <div className="flex min-w-0 flex-wrap items-end gap-3">
        <div className="grid w-full min-w-0 max-w-full gap-1 text-sm sm:w-[min(100%,36rem)]">
          目标群聊
          <SearchSelect
            label="选择增量群聊"
            value={vm.selectedIncrSessionKey}
            options={
              vm.incrGroupOptions.length
                ? vm.incrGroupOptions
                : incrGroups.length
                  ? incrGroups.map((group) => ({ value: group, label: `群名未记录（${group}）` }))
                  : [{ value: "", label: "暂无增量群聊" }]
            }
            disabled={busy || !incrGroups.length}
            onChange={vm.handleSelectIncrSession}
          />
        </div>
        <Button
          variant="outline"
          disabled={loadingIncremental || busy}
          onClick={() => {
            void vm.refreshIncrGroups();
            if (selectedIncrGroup) void vm.loadIncrementalData(selectedIncrGroup);
          }}
        >
          <IconRefresh aria-hidden="true" className={loadingIncremental ? "animate-spin" : ""} />
          刷新
        </Button>
        {selectedIncrGroup && (
          <Button
            variant="ghost"
            className="text-destructive hover:bg-destructive/10 sm:ml-auto"
            disabled={busy || loadingIncremental}
            onClick={() => {
              vm.clearIncrementalMutationError();
              setConfirmation({
                kind: "reset",
                groupId: selectedIncrGroup,
                platformId: selectedIncrPlatform,
              });
            }}
          >
            <IconTrash aria-hidden="true" />
            重置本群增量状态
          </Button>
        )}
      </div>
      {(vm.incrGroupsError || vm.incrementalError) && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.incrGroupsError || vm.incrementalError}
        </p>
      )}
      {selectedIncrGroup && incrCursor && (
        <IncrementalCursorCards cursor={incrCursor} batchCount={vm.incrPagination.total} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="m-0 text-base font-medium">
          增量批次{" "}
          <span className="ml-2 text-sm text-muted-foreground">{vm.incrPagination.total} 个</span>
        </h3>
        <Button variant="outline" disabled={busy} onClick={() => setImporting(true)}>
          导入 / 新建增量批次
        </Button>
      </div>
      {selectedIncrGroup ? (
        <>
          <RecordSelectionActions vm={selection} label="增量批次" />
          {loadingIncremental && (
            <p role="status" className="m-0 text-sm text-muted-foreground">
              正在读取增量批次…
            </p>
          )}
          <div
            className="overflow-x-auto rounded-xl border border-border"
            tabIndex={0}
            role="region"
            aria-label="增量批次列表"
          >
            <table className="w-full min-w-[1050px] text-left text-sm">
              <thead className="bg-muted/60 text-muted-foreground">
                <tr>
                  <th className="w-10 p-3 font-medium">
                    <input
                      type="checkbox"
                      aria-label="选择本页批次（最多 200）"
                      className="size-4 accent-primary focus-visible:outline-2 focus-visible:outline-ring"
                      checked={
                        allKeys.length > 0 &&
                        allKeys.filter((key) => selection.keys.includes(key)).length ===
                          Math.min(allKeys.length, 200)
                      }
                      disabled={busy || loadingIncremental || !allKeys.length}
                      onChange={(event) =>
                        selection.select(
                          event.target.checked
                            ? [...new Set([...selection.keys, ...allKeys])]
                            : selection.keys.filter((key) => !allKeys.includes(key)),
                        )
                      }
                    />
                  </th>
                  {["批次编号", "生成时间", "消息与字符", "提炼话题", "模型消耗", "操作"].map(
                    (name) => (
                      <th key={name} className="p-3 font-medium">
                        {name}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {incrBatches.map((item) => {
                  const key = recordKey({
                    kind: "batch",
                    platform_id: selectedIncrPlatform,
                    group_id: item.group_id,
                    batch_id: item.batch_id,
                  });
                  return (
                    <tr key={key} className="border-t border-border hover:bg-muted/30">
                      <td className="p-3">
                        <input
                          type="checkbox"
                          aria-label={`选择批次 ${item.batch_id}`}
                          className="size-4 accent-primary focus-visible:outline-2 focus-visible:outline-ring"
                          checked={selection.keys.includes(key)}
                          disabled={busy || loadingIncremental}
                          onChange={(event) =>
                            selection.select(
                              event.target.checked
                                ? [...selection.keys, key]
                                : selection.keys.filter((value) => value !== key),
                            )
                          }
                        />
                      </td>
                      <td className="max-w-48 p-3">
                        <span
                          className="block truncate font-mono text-xs text-info"
                          title={item.batch_id}
                        >
                          {item.batch_id}
                        </span>
                      </td>
                      <td className="whitespace-nowrap p-3 text-xs tabular-nums text-muted-foreground">
                        {formatTimestamp(item.timestamp)}
                      </td>
                      <td className="whitespace-nowrap p-3 tabular-nums">
                        <span className="text-info">{item.messages_count.toLocaleString()} 条</span>
                        <div className="text-xs text-muted-foreground">
                          {item.characters_count.toLocaleString()} 字
                        </div>
                      </td>
                      <td className="max-w-64 p-3">
                        <div className="flex flex-wrap gap-1">
                          {item.topics?.length ? (
                            item.topics.map((topic, index) => (
                              <span
                                key={index}
                                title={topic.topic}
                                className="max-w-56 truncate rounded-md bg-warning/10 px-2 py-1 text-xs text-warning"
                              >
                                {topic.topic || "未命名话题"}
                              </span>
                            ))
                          ) : (
                            <span className="text-muted-foreground">无提炼话题</span>
                          )}
                        </div>
                      </td>
                      <td className="whitespace-nowrap p-3 tabular-nums">
                        {item.token_usage?.total_tokens === undefined
                          ? "未记录"
                          : formatTokens(item.token_usage.total_tokens)}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-1.5 whitespace-nowrap">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="bg-info/10 text-info hover:bg-info/15"
                            disabled={loadingIncremental}
                            onClick={() => void vm.handleOpenBatchDetail(item)}
                          >
                            <IconEye aria-hidden="true" />
                            详情
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-creative/20 bg-creative/5 text-creative hover:bg-creative/10"
                            disabled={busy || loadingIncremental}
                            onClick={() =>
                              setManagedLocator({
                                kind: "batch",
                                platform_id: selectedIncrPlatform,
                                group_id: item.group_id,
                                batch_id: item.batch_id,
                              })
                            }
                          >
                            <IconSettings aria-hidden="true" />
                            管理
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:bg-destructive/10"
                            disabled={busy || loadingIncremental}
                            onClick={() => {
                              vm.clearIncrementalMutationError();
                              setConfirmation({
                                kind: "delete",
                                batch: item,
                                platformId: selectedIncrPlatform,
                              });
                            }}
                          >
                            <IconTrash aria-hidden="true" />
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!loadingIncremental && !incrBatches.length && !vm.incrementalError && (
              <p role="status" className="p-6 text-center text-sm text-muted-foreground">
                当前群暂无增量批次，可能已汇总为日报或尚未触发增量分析。
              </p>
            )}
          </div>
          <Pagination
            {...vm.incrPagination}
            disabled={loadingIncremental || busy}
            onChange={(page, pageSize) => void vm.changeIncrementalPage(page, pageSize)}
          />
        </>
      ) : (
        !vm.incrGroupsError && (
          <p role="status" className="py-6 text-center text-sm text-muted-foreground">
            暂无增量批次，可导入已有数据。
          </p>
        )
      )}
      <ManagedRecordDialog
        locator={managedLocator}
        importKind={importing ? "batch" : undefined}
        onClose={() => {
          setManagedLocator(null);
          setImporting(false);
        }}
        onChanged={() => {
          void vm.refreshIncrGroups();
          void vm.loadIncrementalData(selectedIncrGroup);
        }}
      />
      <Dialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open && !vm.incrementalBusy) setConfirmation(null);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {confirmation?.kind === "reset" ? "确认重置本群增量状态？" : "确认删除该增量批次？"}
          </DialogTitle>
          <DialogDescription>
            {confirmation?.kind === "reset"
              ? "清空所选平台中这个群的全部增量批次并重置分析时间，下次分析将重新拉取消息。"
              : "删除后该批次的话题与统计数据将不再参与汇总计算。"}
          </DialogDescription>
          <p className="m-0 break-all font-mono text-sm">
            {confirmation?.platformId || "平台未记录"} ·{" "}
            {confirmation?.kind === "reset" ? confirmation.groupId : confirmation?.batch.batch_id}
          </p>
          {vm.incrementalMutationError && (
            <p role="alert" className="text-sm text-destructive">
              {vm.incrementalMutationError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={vm.incrementalBusy}
              onClick={() => setConfirmation(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={vm.incrementalBusy}
              onClick={async () => {
                if (!confirmation) return;
                const success =
                  confirmation.kind === "reset"
                    ? await vm.handleResetIncrGroup(confirmation.groupId, confirmation.platformId)
                    : await vm.handleDeleteBatch(
                        confirmation.batch.group_id,
                        confirmation.batch.batch_id,
                        confirmation.platformId,
                      );
                if (success) setConfirmation(null);
              }}
            >
              {vm.incrementalBusy
                ? "正在处理…"
                : confirmation?.kind === "reset"
                  ? "确认重置"
                  : "删除"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
