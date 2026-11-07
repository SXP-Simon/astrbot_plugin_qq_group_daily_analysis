import { Button } from "../../../shared/ui/button";
import { useRef } from "react";
import { Alert } from "../../../shared/ui/alert";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import type { ManagedFile } from "../../../entities/plugin-data/api/managedFilesApi";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useManagedFonts, type ManagedFontRow } from "../model/useManagedFonts";

export function FontMutationDialogs({
  vm,
  replacement,
  removal,
  onCloseReplacement,
  onCloseRemoval,
}: {
  vm: ReturnType<typeof useManagedFonts>;
  replacement: { file: File; existing: ManagedFontRow } | null;
  removal: ManagedFile[] | null;
  onCloseReplacement: () => void;
  onCloseRemoval: () => void;
}) {
  const cancelRemoval = useRef<HTMLButtonElement>(null);
  const affected = vm.groups.filter((group) =>
    removal?.some((file) => group.required.includes(file.name)),
  );
  const themeName = (key: string) => KNOWN_TEMPLATES.find((item) => item.key === key)?.name || key;
  return (
    <>
      <Dialog
        open={!!replacement}
        onOpenChange={(open) => {
          if (!open && !vm.busy) onCloseReplacement();
        }}
      >
        <DialogContent>
          <DialogTitle>替换字体</DialogTitle>
          <DialogDescription>保留原文件名，替换会影响所有引用此字体的模板。</DialogDescription>
          {replacement && (
            <>
              <p className="m-0 break-words text-sm">
                用 {replacement.file.name} 替换 {replacement.existing.name}。
              </p>
              <Alert variant="warning">
                <div>请选择同一字体族的正确版本</div>
                <div>
                  {replacement.existing.themes.length
                    ? `将影响：${replacement.existing.themes.map(themeName).join("、")}`
                    : "将影响引用此字体的自定义模板"}
                </div>
              </Alert>
              {vm.error && <Alert variant="destructive">{vm.error}</Alert>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" disabled={vm.busy} onClick={onCloseReplacement}>
                  取消
                </Button>
                <Button
                  disabled={vm.busy}
                  aria-busy={vm.busy}
                  onClick={async () => {
                    if (await vm.upload(replacement.file, replacement.existing.file))
                      onCloseReplacement();
                  }}
                >
                  {vm.busy ? "正在替换…" : "确认替换"}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!removal}
        onOpenChange={(open) => {
          if (!open && !vm.busy) onCloseRemoval();
        }}
      >
        <DialogContent
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelRemoval.current?.focus();
          }}
        >
          <DialogTitle>
            {removal?.length === 1
              ? `移除 ${removal[0].name}？`
              : `移除所选的 ${removal?.length || 0} 个字体？`}
          </DialogTitle>
          <DialogDescription>
            {affected.length
              ? `将影响 ${affected.length} 个模板：${affected.map((group) => themeName(group.theme)).join("、")}。下次渲染可能使用回退字体，排版可能变化。`
              : "自定义字体移除后，需要手动重新上传才能使用。"}
          </DialogDescription>
          <ul className="m-0 max-h-40 overflow-auto pl-5 font-mono text-xs">
            {removal?.map((file) => (
              <li key={file.name}>{file.name}</li>
            ))}
          </ul>
          {vm.error && <Alert variant="destructive">{vm.error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button
              ref={cancelRemoval}
              variant="outline"
              disabled={vm.busy}
              onClick={onCloseRemoval}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={vm.busy}
              aria-busy={vm.busy}
              onClick={async () => {
                if (removal && (await vm.remove(removal))) onCloseRemoval();
              }}
            >
              {vm.busy ? "正在移除…" : "移除字体"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
