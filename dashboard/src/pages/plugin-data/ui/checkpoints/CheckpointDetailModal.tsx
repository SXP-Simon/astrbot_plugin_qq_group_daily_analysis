import { LoadingState } from "@/shared/ui/loading-state";
import { useEffect, useRef, useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import type { CheckpointDetail } from "@/entities/plugin-data/model/types";
import { formatBytes, formatStageName, formatTimestamp } from "@/shared/lib/formatters";
import { copyToClipboard } from "@/shared/lib/clipboard";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/shared/ui/dialog";

export function CheckpointDetailModal({
  open,
  onClose,
  ckptDetail,
  loading,
  error,
  onRetry,
}: {
  open: boolean;
  onClose: () => void;
  ckptDetail: CheckpointDetail | null;
  loading: boolean;
  error?: string;
  onRetry?: () => void;
}) {
  const [copyResult, setCopyResult] = useState("");
  const copyRequest = useRef(0);
  useEffect(() => {
    copyRequest.current += 1;
    setCopyResult("");
    return () => {
      copyRequest.current += 1;
    };
  }, [open, ckptDetail]);
  const bytes = ckptDetail?.data_size_bytes ?? ckptDetail?.data_size;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogTitle>阶段快照详情</DialogTitle>
        <DialogDescription>{formatStageName(ckptDetail?.stage_name)}</DialogDescription>
        {loading ? (
          <LoadingState>正在读取快照…</LoadingState>
        ) : error ? (
          <div className="grid gap-3">
            <p role="alert" className="m-0 text-sm text-destructive">
              {error}
            </p>
            {onRetry && (
              <Button variant="outline" className="w-fit" onClick={onRetry}>
                重新读取
              </Button>
            )}
          </div>
        ) : ckptDetail ? (
          <div className="grid gap-4 text-sm">
            <dl className="m-0 grid gap-3 sm:grid-cols-2">
              {[
                ["群聊", ckptDetail.group_id],
                ["分析归属日期", ckptDetail.date_str],
                ["阶段标识", ckptDetail.stage_name],
                ["产物大小", bytes === undefined ? "未记录" : formatBytes(bytes)],
                [
                  "写入时间",
                  ckptDetail.created_at_formatted ||
                    (ckptDetail.created_at === undefined
                      ? "未记录"
                      : formatTimestamp(ckptDetail.created_at)),
                ],
                ["任务编号", ckptDetail.trace_id || "按天保存，未关联任务"],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="m-0 mt-1 break-all font-mono text-xs">{value}</dd>
                </div>
              ))}
            </dl>
            {ckptDetail.trace_id && (
              <Button
                variant="outline"
                size="sm"
                className="w-fit"
                onClick={async () => {
                  const request = ++copyRequest.current;
                  const copied = await copyToClipboard(ckptDetail.trace_id!);
                  if (request === copyRequest.current)
                    setCopyResult(copied ? "已复制任务编号" : "复制失败，可手动选择编号复制。");
                }}
              >
                <IconCopy aria-hidden="true" />
                复制任务编号
              </Button>
            )}
            <section aria-label="阶段产物数据">
              <h3 className="mb-2 mt-0 text-base font-medium">阶段产物数据（JSON）</h3>
              {ckptDetail.data === undefined ? (
                <p className="text-muted-foreground">未记录产物数据。</p>
              ) : (
                <pre
                  tabIndex={0}
                  className="m-0 max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-muted p-3 font-mono text-xs focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {JSON.stringify(ckptDetail.data, null, 2)}
                </pre>
              )}
            </section>
          </div>
        ) : (
          <p>没有可显示的快照数据。</p>
        )}
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span role="status" className="mr-auto text-sm text-muted-foreground">
            {copyResult}
          </span>
          <Button
            variant="outline"
            disabled={loading || !!error || ckptDetail?.data === undefined}
            onClick={async () => {
              const request = ++copyRequest.current;
              const copied = await copyToClipboard(JSON.stringify(ckptDetail?.data, null, 2));
              if (request === copyRequest.current)
                setCopyResult(copied ? "已复制产物数据" : "复制失败，可手动选择数据复制。");
            }}
          >
            <IconCopy aria-hidden="true" />
            复制产物数据
          </Button>
          <Button onClick={onClose}>关闭详情</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
