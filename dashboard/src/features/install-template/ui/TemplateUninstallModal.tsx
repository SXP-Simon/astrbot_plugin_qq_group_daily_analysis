import { LoadingState } from "../../../shared/ui/loading-state";
import { IconRefresh, IconTrash } from "@tabler/icons-react";
import { templateCapabilities } from "../../../entities/report/model/templates";
import { useTemplateRemoval } from "../model/useTemplateRemoval";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";

interface TemplateUninstallModalProps {
  open: boolean;
  onClose: () => void;
  onUninstalled?: (name: string) => void;
}
export function TemplateUninstallModal({
  open,
  onClose,
  onUninstalled,
}: TemplateUninstallModalProps) {
  const vm = useTemplateRemoval(open, onClose, onUninstalled);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) vm.close();
      }}
    >
      <DialogContent
        className="max-w-2xl"
        onEscapeKeyDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (vm.target) vm.select(null);
          else vm.close();
        }}
        onPointerDownOutside={(event) => {
          if (vm.busy) event.preventDefault();
        }}
      >
        <DialogTitle>卸载自定义模板</DialogTitle>
        <DialogDescription>
          手动放置的自定义模板也可移除。将删除整个模板目录及素材，已生成的报告不受影响；使用它的配置需重新选择。内置模板保留。
        </DialogDescription>
        {vm.target ? (
          <div className="grid gap-4 rounded-xl bg-destructive/5 p-4">
            <h3 className="m-0 break-words text-base font-medium">
              确定卸载模板「{vm.target.label || vm.target.id}」？
            </h3>
            <code className="break-all text-sm">{vm.target.id}/</code>
            <p className="m-0 text-sm text-muted-foreground">
              此操作不可恢复。需要保留的源码和素材请先下载。
            </p>
            {vm.actionError && (
              <p role="alert" className="m-0 text-sm text-destructive">
                {vm.actionError}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" disabled={vm.busy} onClick={() => vm.select(null)}>
                返回列表
              </Button>
              <Button variant="destructive" disabled={vm.busy} onClick={() => void vm.remove()}>
                <IconTrash aria-hidden="true" />
                {vm.busy ? "正在卸载…" : "卸载整个模板"}
              </Button>
            </div>
          </div>
        ) : (
          <>
            {vm.error && (
              <p role="alert" className="m-0 rounded-xl bg-warning/10 p-3 text-sm text-warning">
                {vm.error}
              </p>
            )}
            {vm.loading && (
              <LoadingState className="m-0 text-sm text-muted-foreground">
                正在读取自定义模板…
              </LoadingState>
            )}
            <ul
              className="m-0 max-h-96 list-none divide-y divide-border overflow-auto p-0"
              aria-label="可卸载模板"
            >
              {vm.templates.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 py-3">
                  <div className="grid min-w-0 gap-1">
                    <span className="break-words font-medium">{item.label || item.id}</span>
                    <code className="break-all text-xs text-muted-foreground">{item.id}</code>
                    {item.desc && <p className="m-0 text-sm text-muted-foreground">{item.desc}</p>}
                    <span className="text-xs text-secondary-ink">
                      {templateCapabilities(item).join(" / ")}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    disabled={vm.busy || vm.loading}
                    onClick={() => vm.select(item)}
                  >
                    <IconTrash aria-hidden="true" />
                    卸载
                  </Button>
                </li>
              ))}
            </ul>
            {!vm.loading && !vm.error && !vm.templates.length && (
              <p className="m-0 py-6 text-center text-sm text-muted-foreground">
                暂无可移除的自定义模板
              </p>
            )}
            <div className="flex justify-between gap-2">
              <Button
                variant="outline"
                disabled={vm.loading || vm.busy}
                onClick={() => void vm.refresh()}
              >
                <IconRefresh aria-hidden="true" />
                刷新列表
              </Button>
              <Button variant="outline" onClick={vm.close}>
                关闭窗口
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
