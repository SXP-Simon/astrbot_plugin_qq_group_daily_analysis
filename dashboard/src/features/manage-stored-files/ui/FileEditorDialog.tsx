import type { Dispatch, SetStateAction } from "react";
import { IconLoader2, IconAlertTriangle, IconUpload } from "@tabler/icons-react";
import type { useManagedFiles } from "../model/useManagedFiles";
import type { FileDraft } from "../model/fileDraft";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";

export function FileEditorDialog({
  vm,
  editor,
  setEditor,
}: {
  vm: ReturnType<typeof useManagedFiles>;
  editor: FileDraft | null;
  setEditor: Dispatch<SetStateAction<FileDraft | null>>;
}) {
  const prefix =
    vm.partition?.key === "custom_templates" && vm.directory && vm.directory !== "."
      ? `${vm.directory}/`
      : "";
  return (
    <Dialog
      open={!!editor}
      onOpenChange={(open) => {
        if (!open && !vm.busy) vm.cancelEditor();
      }}
    >
      <DialogContent
        className="max-w-4xl"
        onEscapeKeyDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!vm.busy) vm.cancelEditor();
        }}
      >
        <DialogTitle>{editor?.revision ? "替换或编辑文件" : "上传或新建文件"}</DialogTitle>
        <DialogDescription>
          {editor?.revision
            ? "保存将替换原文件；同名替换保持配置路径不变。"
            : "填写分区内相对路径。同名文件不会被覆盖，请从列表打开原文件后替换。"}
        </DialogDescription>
        {editor?.revision && (
          <p className="m-0 flex gap-2 rounded-xl bg-warning/10 p-3 text-sm text-warning">
            <IconAlertTriangle size={18} aria-hidden="true" className="shrink-0" />
            请先下载备份，保存后立即使用新内容。
          </p>
        )}
        {vm.actionError && (
          <p role="alert" className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {vm.actionError}
          </p>
        )}
        <label className="grid gap-2 text-sm">
          文件相对路径
          {prefix && <code className="break-all text-xs text-muted-foreground">{prefix}</code>}
          <Input
            aria-label="文件相对路径"
            placeholder={
              prefix
                ? "例如 report.typ 或 assets/character.png"
                : "例如 my_theme/report.typ；素材须使用清单中的文件名"
            }
            value={
              prefix && editor?.name.startsWith(prefix)
                ? editor.name.slice(prefix.length)
                : editor?.name || ""
            }
            disabled={!!editor?.revision || vm.busy || vm.uploading}
            onChange={(event) =>
              setEditor((value) => value && { ...value, name: prefix + event.target.value })
            }
          />
        </label>
        {editor?.encoded !== undefined ? (
          <label className="grid gap-2 text-sm">
            选择替换内容
            <Input
              type="file"
              aria-label="选择替换内容"
              disabled={vm.busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void vm.prepareUpload(file, true);
              }}
            />
            <span className="flex gap-2 text-muted-foreground">
              {vm.uploading ? (
                <IconLoader2
                  size={16}
                  aria-hidden="true"
                  className="animate-spin motion-reduce:animate-none"
                />
              ) : (
                <IconUpload size={16} aria-hidden="true" />
              )}
              {vm.uploading ? "正在读取所选文件…" : "已载入文件内容，可选择新的替换文件。"}
            </span>
          </label>
        ) : (
          <label className="grid gap-2 text-sm">
            文件内容
            <textarea
              aria-label="文件内容"
              value={editor?.text || ""}
              rows={18}
              spellCheck={false}
              readOnly={vm.busy}
              className="max-h-[50dvh] min-h-48 w-full resize-y rounded-xl border border-solid border-input bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onChange={(event) =>
                setEditor((value) => value && { ...value, text: event.target.value })
              }
            />
          </label>
        )}
        <p className="m-0 text-sm text-muted-foreground">
          {vm.partition?.key === "custom_templates"
            ? "源码和素材按相对路径引用，请保留模板入口及引用关系。"
            : vm.partition?.key === "template_resources"
              ? "文件路径须与主题素材清单一致，可在素材状态页展开清单并复制路径。"
              : "同名替换会保留原配置引用路径。"}
          单文件最大 32 MiB，图片会校验格式与像素预算。
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" disabled={vm.busy} onClick={vm.cancelEditor}>
            取消
          </Button>
          <Button
            disabled={vm.busy || vm.uploading || !editor?.name.trim()}
            onClick={() => void vm.saveEditor()}
          >
            {vm.busy ? "正在保存…" : "保存"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
