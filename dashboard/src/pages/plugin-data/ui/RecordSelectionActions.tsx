import { useState } from "react";
import { IconTrash } from "@tabler/icons-react";
import type { useRecordSelection } from "../model/useRecordSelection";
import type { RecordLocator } from "../../../entities/plugin-data/api/managedRecordsApi";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";

export function RecordSelectionActions({
  vm,
  label,
}: {
  vm: ReturnType<typeof useRecordSelection>;
  label: string;
}) {
  const action = label === "头像缓存" ? "清理" : "删除";
  const [targets, setTargets] = useState<RecordLocator[] | null>(null);
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="mr-auto text-muted-foreground">
          已选 {vm.selected.length} 项（最多 200）{vm.busy ? ` · 已处理 ${vm.progress}` : ""}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={!vm.selected.length || vm.busy}
          onClick={vm.clear}
        >
          取消选择
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-destructive hover:bg-destructive/10"
          disabled={!vm.selected.length || vm.busy}
          onClick={() => setTargets([...vm.selected])}
        >
          <IconTrash aria-hidden="true" />
          {action}所选
        </Button>
      </div>
      {vm.result && (
        <div
          role="status"
          className={`rounded-lg p-3 text-sm ${vm.result.failed.length ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}
        >
          <p className="m-0">
            {action}成功 {vm.result.deleted} 项，失败 {vm.result.failed.length} 项
          </p>
          {vm.result.failed.length > 0 && (
            <ul className="mb-0 mt-2 max-h-48 overflow-auto pl-4">
              {vm.result.failed.map((item, index) => (
                <li key={`${item.name}-${index}`} className="break-words">
                  {item.name}：{item.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Dialog
        open={targets !== null}
        onOpenChange={(open) => {
          if (!open && !vm.busy) setTargets(null);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {action}所选 {targets?.length ?? 0} 项{label}？
          </DialogTitle>
          <DialogDescription>
            {label === "头像缓存"
              ? "只清理所选头像缓存，下次使用时会重新获取。"
              : "只删除确认的这些记录。批次和快照删除会影响汇总与续跑；正在执行任务的群聊会拒绝操作。"}
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="outline" disabled={vm.busy} onClick={() => setTargets(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={vm.busy}
              onClick={async () => {
                if (!targets) return;
                await vm.remove(targets);
                setTargets(null);
              }}
            >
              {vm.busy ? `已处理 ${vm.progress} / ${targets?.length ?? 0}` : `${action}所选`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
