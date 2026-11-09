import type { ManagedFile, ManagedPartition } from "@/entities/plugin-data/api/managedFilesApi";
import type { useManagedFiles } from "@/features/manage-stored-files/model/useManagedFiles";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/shared/ui/dialog";

export function ManagedFileDeleteDialog({
  vm,
  partition,
  deletion,
  onClose,
  fileAction,
}: {
  vm: ReturnType<typeof useManagedFiles>;
  partition: ManagedPartition;
  deletion: { partition: string; directory: string; files: ManagedFile[] } | null;
  onClose: () => void;
  fileAction: string;
}) {
  return (
    <Dialog
      open={!!deletion}
      onOpenChange={(open) => {
        if (!open && !vm.busy) onClose();
      }}
    >
      <DialogContent
        onEscapeKeyDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!vm.busy) onClose();
        }}
        onPointerDownOutside={(event) => {
          if (vm.busy) event.preventDefault();
        }}
      >
        <DialogTitle>
          {fileAction}已选的 {deletion?.files.length ?? 0} 个文件？
        </DialogTitle>
        <DialogDescription>
          {partition.name}
          {vm.directory && ` / ${vm.directory}`}。{partition.impact}
        </DialogDescription>
        <ul className="m-0 max-h-56 overflow-auto pl-5 text-sm">
          {deletion?.files.map((file) => (
            <li key={file.name} className="break-all">
              {file.name}
            </li>
          ))}
        </ul>
        {vm.actionError && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {vm.actionError}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" disabled={vm.busy} onClick={() => onClose()}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={vm.busy}
            onClick={async () => {
              if (deletion && (await vm.deleteSelected(deletion.files, deletion.partition)))
                onClose();
            }}
          >
            {vm.busy ? "正在处理…" : `${fileAction}所选`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
