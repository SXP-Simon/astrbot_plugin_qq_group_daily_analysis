import { useEffect, useState } from "react";
import { IconCode, IconSettings, IconTrash } from "@tabler/icons-react";
import { ManagedRecordDialog } from "../ManagedRecordDialog";
import { RecordSelectionActions } from "../RecordSelectionActions";
import { useRecordSelection, recordKey } from "../../model/useRecordSelection";
import type { RecordLocator } from "../../../../entities/plugin-data/api/managedRecordsApi";
import type { CheckpointItem } from "../../../../entities/plugin-data/model/types";
import type { usePluginDataViewModel } from "../../model/usePluginDataViewModel";
import { formatBytes, formatTimestamp, formatStageName } from "../../../../shared/lib/formatters";
import { Button } from "../../../../shared/ui/button";
import { Input } from "../../../../shared/ui/input";
import { Pagination } from "../../../../shared/ui/pagination";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../../../../shared/ui/dialog";
import { CheckpointFilterBar } from "./CheckpointFilterBar";

export function CheckpointsTab({ vm }: { vm: ReturnType<typeof usePluginDataViewModel> }) {
  const [managedLocator, setManagedLocator] = useState<RecordLocator | null>(null);
  const [deleting, setDeleting] = useState<CheckpointItem | null>(null);
  const [jump, setJump] = useState("");
  const locators: RecordLocator[] = vm.checkpoints.map((item) => ({
    kind: "checkpoint",
    group_id: item.group_id,
    date_str: item.date_str,
    stage_name: item.stage_name,
    trace_id: item.trace_id || "",
  }));
  const selection = useRecordSelection(locators, () => {
    void vm.loadCheckpoints();
    void vm.refreshCheckpointGroups();
  });
  const clear = selection.clear;
  useEffect(() => {
    clear();
  }, [vm.ckptFilterPlatform, vm.ckptFilterGroup, vm.ckptFilterDate, vm.ckptFilterStage, clear]);
  const keys = locators.map(recordKey);
  const busy = selection.busy || vm.checkpointDeleting;
  return (
    <div className="grid min-w-0 gap-4">
      <CheckpointFilterBar vm={vm} />
      <RecordSelectionActions vm={selection} label="阶段快照" />
      {vm.checkpointError && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.checkpointError}
        </p>
      )}
      {vm.loadingCheckpoints && (
        <p role="status" className="m-0 text-sm text-muted-foreground">
          正在读取阶段快照…
        </p>
      )}
      <div
        className="overflow-x-auto rounded-xl border border-border"
        tabIndex={0}
        role="region"
        aria-label="阶段快照列表"
      >
        <table className="w-full min-w-[1100px] text-left text-sm">
          <thead className="bg-muted/60 text-muted-foreground">
            <tr>
              <th className="w-10 p-3 font-medium">
                <input
                  type="checkbox"
                  aria-label="选择本页快照"
                  className="size-4 accent-primary"
                  checked={keys.length > 0 && keys.every((key) => selection.keys.includes(key))}
                  disabled={busy || vm.loadingCheckpoints || !keys.length}
                  onChange={(event) =>
                    selection.select(
                      event.target.checked
                        ? [...new Set([...selection.keys, ...keys])]
                        : selection.keys.filter((key) => !keys.includes(key)),
                    )
                  }
                />
              </th>
              {["群聊", "分析日期", "阶段", "任务编号", "产物大小", "写入时间", "操作"].map(
                (label) => (
                  <th key={label} className="p-3 font-medium">
                    {label}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {vm.checkpoints.map((item, index) => {
              const key = keys[index];
              const bytes = item.data_size_bytes ?? item.data_size;
              return (
                <tr key={key} className="border-t border-border hover:bg-muted/30">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      aria-label={`选择快照 ${item.group_id} ${item.date_str} ${item.stage_name} ${item.trace_id || "按天"}`}
                      checked={selection.keys.includes(key)}
                      disabled={busy || vm.loadingCheckpoints}
                      onChange={(event) =>
                        selection.select(
                          event.target.checked
                            ? [...selection.keys, key]
                            : selection.keys.filter((value) => value !== key),
                        )
                      }
                    />
                  </td>
                  <td className="max-w-56 break-words p-3">
                    <span>{item.group_name || "未记录群名"}</span>
                    <span className="mt-1 block break-all font-mono text-xs text-muted-foreground">
                      {item.platform || "未记录平台"} · {item.group_id}
                    </span>
                  </td>
                  <td className="whitespace-nowrap p-3 text-xs tabular-nums">{item.date_str}</td>
                  <td className="p-3">
                    <span className="text-creative">{formatStageName(item.stage_name)}</span>
                    <div className="mt-1 font-mono text-xs text-muted-foreground">
                      {item.stage_name}
                    </div>
                  </td>
                  <td className="max-w-44 break-all p-3 font-mono text-xs text-info">
                    {item.trace_id || "按天保存，未关联任务"}
                  </td>
                  <td className="whitespace-nowrap p-3 tabular-nums">
                    {bytes === undefined ? "未记录" : formatBytes(bytes)}
                  </td>
                  <td className="whitespace-nowrap p-3 text-xs text-muted-foreground">
                    {item.created_at_formatted ||
                      (item.created_at === undefined
                        ? item.updated_at || "未记录"
                        : formatTimestamp(item.created_at))}
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1.5 whitespace-nowrap">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="bg-info/10 text-info hover:bg-info/15"
                        disabled={vm.loadingCheckpoints}
                        onClick={() => void vm.handleOpenCkptDetail(item)}
                      >
                        <IconCode aria-hidden="true" />
                        产物 JSON
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-creative/20 bg-creative/5 text-creative hover:bg-creative/10"
                        disabled={busy || vm.loadingCheckpoints}
                        onClick={() => setManagedLocator(locators[index])}
                      >
                        <IconSettings aria-hidden="true" />
                        管理
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:bg-destructive/10"
                        disabled={busy || vm.loadingCheckpoints}
                        onClick={() => {
                          vm.clearCheckpointDeleteError();
                          setDeleting(item);
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
        {!vm.loadingCheckpoints && !vm.checkpoints.length && !vm.checkpointError && (
          <p role="status" className="p-6 text-center text-sm text-muted-foreground">
            没有符合条件的阶段快照。
          </p>
        )}
      </div>
      <Pagination
        page={vm.checkpointsPage}
        pageSize={vm.checkpointsPageSize}
        total={vm.checkpointsTotal}
        pageSizes={[10, 20, 50, 100]}
        disabled={vm.loadingCheckpoints || busy}
        onChange={(page, pageSize) => void vm.loadCheckpoints({ page, pageSize })}
      />
      {vm.checkpointsTotal > vm.checkpointsPageSize && (
        <form
          className="flex items-center justify-end gap-2 text-sm"
          onSubmit={(event) => {
            event.preventDefault();
            const page = Number(jump);
            if (Number.isInteger(page) && page >= 1)
              void vm.loadCheckpoints({
                page: Math.min(page, Math.ceil(vm.checkpointsTotal / vm.checkpointsPageSize)),
              });
          }}
        >
          <label htmlFor="checkpoint-page">跳到页码</label>
          <Input
            id="checkpoint-page"
            type="number"
            min={1}
            max={Math.ceil(vm.checkpointsTotal / vm.checkpointsPageSize)}
            value={jump}
            onChange={(event) => setJump(event.target.value)}
            className="w-20"
          />
          <Button variant="outline" type="submit" disabled={vm.loadingCheckpoints || busy || !jump}>
            跳转
          </Button>
        </form>
      )}
      <ManagedRecordDialog
        locator={managedLocator}
        onClose={() => setManagedLocator(null)}
        onChanged={() => {
          void vm.loadCheckpoints();
          void vm.refreshCheckpointGroups();
        }}
      />
      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open && !vm.checkpointDeleting) setDeleting(null);
        }}
      >
        <DialogContent>
          <DialogTitle>确认删除该阶段快照？</DialogTitle>
          <DialogDescription>
            删除后无法再使用这份产物续跑或重绘，其他阶段快照不受影响。
          </DialogDescription>
          <p className="m-0 break-all text-sm">
            {deleting?.group_id} · {deleting?.date_str} · {formatStageName(deleting?.stage_name)}
            <br />
            {deleting?.trace_id || "按天保存，未关联任务"}
          </p>
          {vm.checkpointDeleteError && (
            <p role="alert" className="text-sm text-destructive">
              {vm.checkpointDeleteError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={vm.checkpointDeleting}
              onClick={() => setDeleting(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={vm.checkpointDeleting}
              onClick={async () => {
                if (
                  deleting &&
                  (await vm.handleDeleteCheckpoint(
                    deleting.group_id,
                    deleting.date_str,
                    deleting.stage_name,
                    deleting.trace_id,
                  ))
                )
                  setDeleting(null);
              }}
            >
              {vm.checkpointDeleting ? "正在删除…" : "删除"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
