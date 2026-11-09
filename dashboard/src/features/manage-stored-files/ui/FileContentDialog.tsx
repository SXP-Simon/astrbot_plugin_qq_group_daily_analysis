import { HtmlPreview } from "@/shared/ui/html-preview";
import { ImagePreview } from "@/shared/ui/image-preview";
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { IconAlertTriangle, IconDownload, IconEdit } from "@tabler/icons-react";
import type { useManagedFiles } from "@/features/manage-stored-files/model/useManagedFiles";
import type { ManagedFileContent } from "@/entities/plugin-data/api/managedFilesApi";
import { FileEditorDialog } from "./FileEditorDialog";
import type { FileDraft } from "@/features/manage-stored-files/model/fileDraft";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/shared/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/shared/ui/tabs";

type Props = {
  vm: ReturnType<typeof useManagedFiles>;
  editor: FileDraft | null;
  setEditor: Dispatch<SetStateAction<FileDraft | null>>;
  references?: string[];
};
export function FileContentDialog(props: Props) {
  return props.vm.content ? (
    <ContentDialog
      key={`${props.vm.content.name}:${props.vm.content.revision}`}
      {...props}
      content={props.vm.content}
    />
  ) : null;
}
function ContentDialog({
  vm,
  editor,
  setEditor,
  references,
  content,
}: Props & { content: ManagedFileContent }) {
  const [rename, setRename] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [preview, setPreview] = useState({ url: "", error: "" });
  const currentFile = vm.files.find((file) => file.name === content.name);
  const prefix =
    vm.partition?.key === "custom_templates" && vm.directory && vm.directory !== "."
      ? `${vm.directory}/`
      : "";
  useEffect(() => {
    let url = "";
    try {
      const bytes = Uint8Array.from(atob(content.content_base64), (char) => char.charCodeAt(0));
      url = URL.createObjectURL(new Blob([bytes], { type: content.media_type }));
      setPreview({ url, error: "" });
    } catch {
      setPreview({ url: "", error: "文件内容无法解码，请重新读取后重试。" });
    }
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [content]);
  const childOpen = !!editor || rename !== null || zoom;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !vm.busy && !childOpen) vm.setContent(null);
      }}
    >
      <DialogContent
        className="max-w-4xl"
        onEscapeKeyDown={(event) => {
          if (childOpen) {
            event.preventDefault();
            event.stopPropagation();
            if (!vm.busy) {
              if (editor) vm.cancelEditor();
              else if (rename !== null) setRename(null);
              else setZoom(false);
            }
          }
        }}
      >
        <DialogTitle className="break-all font-mono text-base">{content.name}</DialogTitle>
        <DialogDescription>查看文件内容，下载后可保留原件。</DialogDescription>
        {!!references?.length && (
          <div className="rounded-xl bg-warning/10 p-3 text-sm text-warning">
            <p className="m-0 flex gap-2">
              <IconAlertTriangle size={18} aria-hidden="true" className="shrink-0" />
              此图片被配置引用；同名替换保留引用，重命名或删除会使旧路径失效。
            </p>
            <p className="mb-0 mt-2 break-all">{references.join("、")}</p>
          </div>
        )}
        {vm.actionError && !childOpen && (
          <p role="alert" className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {vm.actionError}
          </p>
        )}
        {preview.error ? (
          <div role="alert" className="text-sm text-destructive">
            {preview.error}
            <Button
              variant="outline"
              className="ml-2"
              disabled={vm.busy}
              onClick={() => void vm.inspect(content.name)}
            >
              重新读取
            </Button>
          </div>
        ) : content.media_type.startsWith("image/") ? (
          <>
            <button
              type="button"
              aria-label="放大图片"
              className="cursor-zoom-in overflow-hidden rounded-xl border border-border bg-muted/40 p-2 focus-visible:outline-2 focus-visible:outline-ring"
              onClick={() => setZoom(true)}
            >
              <img
                src={preview.url || undefined}
                alt={content.name}
                className="mx-auto max-h-[50dvh] max-w-full object-contain"
              />
              <span className="text-sm text-muted-foreground">放大查看</span>
            </button>
            {zoom && (
              <ImagePreview
                src={preview.url || null}
                title={content.name}
                fitMode="width"
                onClose={() => setZoom(false)}
              />
            )}
          </>
        ) : content.media_type === "text/html" ? (
          <Tabs defaultValue="preview">
            <TabsList aria-label="HTML 查看方式">
              <TabsTrigger value="preview">隔离预览</TabsTrigger>
              <TabsTrigger value="source">HTML 源码</TabsTrigger>
            </TabsList>
            <TabsContent value="preview">
              <HtmlPreview
                title="报告预览"
                sandbox=""
                html={content.text || ""}
                className="h-[50dvh] min-h-64 w-full rounded-xl border border-border bg-white"
              />
            </TabsContent>
            <TabsContent value="source">
              <textarea
                aria-label="HTML 源码"
                readOnly
                value={content.text || ""}
                rows={18}
                className="max-h-[50dvh] w-full rounded-xl border border-input bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground focus-visible:outline-2 focus-visible:outline-ring"
              />
            </TabsContent>
          </Tabs>
        ) : content.text !== null ? (
          <textarea
            aria-label="文件源码"
            readOnly
            value={content.text}
            rows={18}
            className="max-h-[50dvh] w-full rounded-xl border border-input bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          />
        ) : (
          <p className="text-sm text-muted-foreground">此二进制文件可下载后使用对应应用查看。</p>
        )}
        {deleting && (
          <section
            aria-label="删除文件确认"
            className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm"
          >
            <h3 className="m-0 text-base font-medium text-destructive">删除此文件？</h3>
            <code className="break-all">{content.name}</code>
            <p className="m-0">{vm.partition?.impact}</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" disabled={vm.busy} onClick={() => setDeleting(false)}>
                取消删除
              </Button>
              <Button
                variant="destructive"
                disabled={vm.busy}
                onClick={() =>
                  void vm.mutate({
                    operation: "delete",
                    name: content.name,
                    revision: content.revision,
                  })
                }
              >
                {vm.busy ? "正在删除…" : "确认删除"}
              </Button>
            </div>
          </section>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={!preview.url || vm.busy}
            onClick={() => {
              const link = document.createElement("a");
              link.href = preview.url;
              link.download = content.name.split("/").pop() || "download";
              link.click();
            }}
          >
            <IconDownload aria-hidden="true" />
            下载原文件
          </Button>
          {currentFile?.editable && (
            <Button
              variant="outline"
              disabled={vm.busy || deleting}
              onClick={() => {
                vm.clearActionError();
                setEditor({
                  name: content.name,
                  text: content.text || "",
                  revision: content.revision,
                });
              }}
            >
              <IconEdit aria-hidden="true" />
              编辑源码
            </Button>
          )}
          {vm.partition?.writable && (
            <Button
              variant="outline"
              disabled={vm.busy || deleting}
              onClick={() => {
                vm.clearActionError();
                setEditor({
                  name: content.name,
                  text: content.text || "",
                  revision: content.revision,
                  encoded: content.content_base64,
                });
              }}
            >
              替换文件
            </Button>
          )}
          {["custom_templates", "config_files"].includes(vm.partition?.key || "") && (
            <Button
              variant="outline"
              disabled={vm.busy || deleting}
              onClick={() => {
                vm.clearActionError();
                setRename(content.name);
              }}
            >
              重命名
            </Button>
          )}
          {vm.partition?.deletable && !deleting && (
            <Button
              variant="ghost"
              className="text-destructive hover:bg-destructive/10"
              disabled={vm.busy}
              onClick={() => {
                vm.clearActionError();
                setDeleting(true);
              }}
            >
              删除文件
            </Button>
          )}
          <Button
            className="ml-auto"
            variant="outline"
            disabled={vm.busy}
            onClick={() => vm.setContent(null)}
          >
            关闭文件
          </Button>
        </div>
        <FileEditorDialog vm={vm} editor={editor} setEditor={setEditor} />
        <Dialog
          open={rename !== null}
          onOpenChange={(open) => {
            if (!open && !vm.busy) setRename(null);
          }}
        >
          <DialogContent
            onEscapeKeyDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
              if (!vm.busy) setRename(null);
            }}
          >
            <DialogTitle>重命名文件</DialogTitle>
            <DialogDescription>重命名后，模板或配置中引用的旧路径需要同步更新。</DialogDescription>
            {vm.actionError && (
              <p role="alert" className="m-0 text-sm text-destructive">
                {vm.actionError}
              </p>
            )}
            <label className="grid gap-2 text-sm">
              新文件名
              {prefix && <code className="break-all text-xs text-muted-foreground">{prefix}</code>}
              <Input
                aria-label="新文件名"
                value={
                  prefix && rename?.startsWith(prefix) ? rename.slice(prefix.length) : rename || ""
                }
                disabled={vm.busy}
                onChange={(event) => setRename(prefix + event.target.value)}
              />
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="outline" disabled={vm.busy} onClick={() => setRename(null)}>
                取消
              </Button>
              <Button
                disabled={vm.busy || !rename?.trim() || rename === content.name}
                onClick={async () => {
                  if (
                    rename &&
                    (await vm.mutate({
                      operation: "rename",
                      name: content.name,
                      revision: content.revision,
                      new_name: rename,
                    }))
                  )
                    setRename(null);
                }}
              >
                {vm.busy ? "正在重命名…" : "重命名"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
