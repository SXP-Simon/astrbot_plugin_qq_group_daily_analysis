import { LoadingState } from "../../../shared/ui/loading-state";
import { useEffect, useRef, useState } from "react";
import {
  IconAlertTriangle,
  IconCopy,
  IconDownload,
  IconEdit,
  IconTrash,
  IconZoomIn,
} from "@tabler/icons-react";
import { useManagedRecord } from "../model/useManagedRecord";
import type { RecordLocator } from "../../../entities/plugin-data/api/managedRecordsApi";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";
import { copyToClipboard } from "../../../shared/lib/clipboard";

type Props = {
  locator: RecordLocator | null;
  importKind?: string;
  onClose: () => void;
  onChanged: () => void;
};

export function ManagedRecordDialog(props: Props) {
  // 条目切换时同时清空编辑稿、删除确认和图片预览状态。
  return <RecordDialog key={JSON.stringify([props.locator, props.importKind])} {...props} />;
}

function RecordDialog({ locator, importKind, onClose, onChanged }: Props) {
  const vm = useManagedRecord(locator, onChanged, onClose, importKind);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [copyResult, setCopyResult] = useState("");
  const copyRequest = useRef(0);
  useEffect(() => {
    const request = copyRequest;
    return () => {
      request.current++;
    };
  }, []);
  const kind = locator?.kind || importKind;
  const avatar =
    vm.record?.data &&
    typeof vm.record.data === "object" &&
    !Array.isArray(vm.record.data) &&
    "data_uri" in vm.record.data
      ? vm.record.data.data_uri
      : null;
  const warning =
    kind === "avatar"
      ? "头像缓存删除后将按需重新获取；数据库文件保持完整。"
      : kind === "checkpoint"
        ? "只修改 data 内的阶段产物。任务归属、创建时间和有效期不可修改，错误内容可能影响断点续跑。"
        : kind === "batch"
          ? "修改批次会影响后续汇总，保存不会移动消息游标。请保持群组、批次身份及各计数与原消息一致。"
          : "删除最新存档会回退每日索引，不会删除报告图片或任务统计。";
  return (
    <Dialog
      open={!!locator || !!importKind}
      onOpenChange={(open) => {
        if (!open && !vm.busy && !zoom) onClose();
      }}
    >
      <DialogContent
        className={kind === "avatar" ? "max-w-xl" : "max-w-4xl"}
        onEscapeKeyDown={(event) => {
          if (zoom) {
            event.preventDefault();
            setZoom(false);
          }
        }}
      >
        <DialogTitle>
          {kind === "avatar" ? "头像缓存详情" : importKind ? "导入业务记录" : "业务记录详情与修订"}
        </DialogTitle>
        <DialogDescription>
          {importKind
            ? "粘贴此前导出的完整 JSON（locator + data），导入不会覆盖已有记录。快照由分析任务创建，不提供新建入口。"
            : "查看、导出或修订当前记录。"}
        </DialogDescription>
        <p className="m-0 flex items-start gap-2 rounded-xl bg-warning/10 p-3 text-sm text-warning">
          <IconAlertTriangle size={18} className="shrink-0" aria-hidden="true" />
          {warning}
        </p>
        {vm.error && (
          <div role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            <p className="m-0 whitespace-pre-wrap break-words">{vm.error}</p>
            {!vm.record && !importKind && (
              <Button className="mt-2" variant="outline" disabled={vm.busy} onClick={vm.retry}>
                重新读取
              </Button>
            )}
          </div>
        )}
        {vm.busy && !vm.record && !importKind ? (
          <LoadingState>正在读取记录…</LoadingState>
        ) : kind === "avatar" ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <code className="min-w-0 break-all text-xs">{locator?.key}</code>
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  const request = ++copyRequest.current;
                  const copied = await copyToClipboard(locator?.key || "");
                  if (request === copyRequest.current)
                    setCopyResult(copied ? "缓存键已复制" : "复制失败，可选择上方文字复制。");
                }}
              >
                <IconCopy aria-hidden="true" />
                复制缓存键
              </Button>
              <span role="status" className="text-sm text-muted-foreground">
                {copyResult}
              </span>
            </div>
            {typeof avatar === "string" &&
            /^data:image\/(png|jpe?g|webp|gif|svg\+xml|bmp|x-icon);base64,/.test(avatar) ? (
              <>
                <button
                  type="button"
                  className="w-fit cursor-zoom-in rounded-xl border border-solid border-border bg-muted p-2 focus-visible:outline-2 focus-visible:outline-ring"
                  aria-label="放大头像"
                  onClick={() => setZoom(true)}
                >
                  <img src={avatar} alt="缓存头像" className="size-40 object-contain" />
                  <span className="flex items-center justify-center gap-1 text-sm text-muted-foreground">
                    <IconZoomIn size={16} aria-hidden="true" />
                    放大查看
                  </span>
                </button>
                <Dialog open={zoom} onOpenChange={setZoom}>
                  <DialogContent
                    className="max-w-3xl"
                    onEscapeKeyDown={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setZoom(false);
                    }}
                  >
                    <DialogTitle>头像预览</DialogTitle>
                    <DialogDescription>按图片比例展示，可关闭返回记录。</DialogDescription>
                    <img
                      src={avatar}
                      alt="放大的缓存头像"
                      className="mx-auto max-h-[65dvh] max-w-full object-contain"
                    />
                    <Button
                      className="justify-self-end"
                      variant="outline"
                      onClick={() => setZoom(false)}
                    >
                      返回记录
                    </Button>
                  </DialogContent>
                </Dialog>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">暂无可预览的头像，请重新读取条目。</p>
            )}
          </div>
        ) : vm.record || importKind ? (
          <label className="grid gap-2 text-sm">
            {vm.editing ? "编辑业务记录 JSON" : "业务记录 JSON"}
            <textarea
              aria-label="业务记录 JSON"
              value={vm.text}
              readOnly={!vm.editing || vm.busy || confirmDelete}
              onChange={(event) => vm.setText(event.target.value)}
              rows={18}
              spellCheck={false}
              className="max-h-[50dvh] min-h-48 w-full resize-y rounded-xl border border-solid border-input bg-muted/40 p-3 font-mono text-xs leading-relaxed text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
        ) : null}
        {confirmDelete && (
          <section
            aria-label="删除确认"
            className="grid gap-3 rounded-xl border border-solid border-destructive/30 bg-destructive/10 p-3 text-sm"
          >
            <h3 className="m-0 text-base font-medium text-destructive">
              {kind === "avatar" ? "清除此头像缓存？" : "删除此业务记录？"}
            </h3>
            <p className="m-0">
              {kind === "avatar"
                ? "仅移除此平台缓存键的头像，下次需要时重新获取。"
                : "删除会影响历史查阅、批次汇总或断点续跑，请先导出留存。"}
            </p>
            <code className="break-all text-xs">{JSON.stringify(vm.record?.locator)}</code>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" disabled={vm.busy} onClick={() => setConfirmDelete(false)}>
                取消删除
              </Button>
              <Button
                variant="destructive"
                disabled={vm.busy}
                onClick={() => void vm.save("delete")}
              >
                {vm.busy ? "正在删除…" : "确认删除"}
              </Button>
            </div>
          </section>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={!vm.record || vm.busy} onClick={vm.download}>
            <IconDownload aria-hidden="true" />
            {kind === "avatar" ? "下载头像图片" : "导出完整 JSON"}
          </Button>
          {!importKind && kind !== "avatar" && (
            <Button
              variant="outline"
              disabled={!vm.record || vm.busy || confirmDelete}
              onClick={() => vm.setEditing(!vm.editing)}
            >
              <IconEdit aria-hidden="true" />
              {vm.editing ? "退出编辑" : "编辑产物"}
            </Button>
          )}
          {vm.editing && (
            <Button
              disabled={vm.busy || confirmDelete}
              onClick={() => void vm.save(importKind ? "create" : "replace")}
            >
              {vm.busy ? "正在保存…" : importKind ? "导入为新记录" : "保存修订"}
            </Button>
          )}
          {!importKind && !confirmDelete && (
            <Button
              variant="ghost"
              className="text-destructive hover:bg-destructive/10"
              disabled={!vm.record || vm.busy}
              onClick={() => setConfirmDelete(true)}
            >
              <IconTrash aria-hidden="true" />
              {kind === "avatar" ? "清除此头像缓存" : "删除此记录"}
            </Button>
          )}
          <Button className="ml-auto" variant="outline" onClick={onClose} disabled={vm.busy}>
            关闭记录
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
