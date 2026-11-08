import { LoadingState } from "../../../../shared/ui/loading-state";
import { useEffect, useRef, useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import type { IncrementalBatchItem } from "../../../../entities/plugin-data/model/types";
import { batchQualityReviewSchema } from "../../../../entities/plugin-data/model/batchQualityReview";
import { formatTimestamp, formatTokens } from "../../../../shared/lib/formatters";
import { copyToClipboard } from "../../../../shared/lib/clipboard";
import { Button } from "../../../../shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../../../../shared/ui/dialog";

interface BatchDetailModalProps {
  open: boolean;
  onClose: () => void;
  batchDetail: IncrementalBatchItem | null;
  loading: boolean;
  error?: string;
  onRetry?: () => void;
}

export function BatchDetailModal({
  open,
  onClose,
  batchDetail,
  loading,
  error,
  onRetry,
}: BatchDetailModalProps) {
  const [copyResult, setCopyResult] = useState("");
  const copyRequest = useRef(0);
  useEffect(() => {
    copyRequest.current += 1;
    setCopyResult("");
    return () => {
      copyRequest.current += 1;
    };
  }, [open, batchDetail]);
  const review = batchDetail?.chat_quality_review;
  const parsedReview = batchQualityReviewSchema.safeParse(review);
  const quality = parsedReview.success ? parsedReview.data : null;
  const usage = batchDetail?.token_usage;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogTitle>增量批次详情</DialogTitle>
        <DialogDescription className="break-all font-mono">
          {batchDetail?.batch_id || "未选择批次"}
        </DialogDescription>
        {loading ? (
          <LoadingState className="py-6 text-muted-foreground">正在读取批次详情…</LoadingState>
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
        ) : batchDetail ? (
          <div className="grid gap-5 text-sm">
            <dl className="m-0 grid gap-3 sm:grid-cols-2">
              {[
                ["目标群聊", batchDetail.group_id],
                ["生成时间", formatTimestamp(batchDetail.timestamp)],
                [
                  "消息与字符",
                  `${batchDetail.messages_count.toLocaleString()} 条 · ${batchDetail.characters_count.toLocaleString()} 字`,
                ],
                [
                  "最新消息时间",
                  batchDetail.last_message_timestamp
                    ? formatTimestamp(batchDetail.last_message_timestamp)
                    : "未记录",
                ],
                [
                  "总 Tokens",
                  usage?.total_tokens === undefined ? "未记录" : formatTokens(usage.total_tokens),
                ],
                [
                  "输入 / 输出 Tokens",
                  usage
                    ? `${usage.prompt_tokens === undefined ? "未记录" : formatTokens(usage.prompt_tokens)} / ${usage.completion_tokens === undefined ? "未记录" : formatTokens(usage.completion_tokens)}`
                    : "未记录",
                ],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="m-0 mt-1 break-all tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  const request = ++copyRequest.current;
                  const copied = await copyToClipboard(batchDetail.batch_id);
                  if (request === copyRequest.current)
                    setCopyResult(copied ? "已复制批次编号" : "复制失败，可手动选择编号复制。");
                }}
              >
                <IconCopy aria-hidden="true" />
                复制批次编号
              </Button>
            </div>
            {!!review && (
              <section
                aria-label="聊天质量与氛围评价"
                className="grid gap-2 border-0 border-t border-solid border-border pt-4"
              >
                <h3 className="m-0 text-base font-medium">聊天质量与氛围评价</h3>
                {typeof review === "string" ? (
                  <p className="m-0 whitespace-pre-wrap">{review}</p>
                ) : quality ? (
                  <>
                    {(quality.title || quality.subtitle) && (
                      <p className="m-0">
                        {[quality.title, quality.subtitle].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    {quality.summary && (
                      <p className="m-0 whitespace-pre-wrap text-muted-foreground">
                        {quality.summary}
                      </p>
                    )}
                    {Array.isArray(quality.dimensions) ? (
                      quality.dimensions.map((dimension, index) => (
                        <div key={index} className="grid gap-1">
                          <span className="text-primary-ink">
                            {dimension.name || `维度 ${index + 1}`} ·{" "}
                            {dimension.percentage === undefined
                              ? "未记录"
                              : `${dimension.percentage}%`}
                          </span>
                          <p className="m-0 whitespace-pre-wrap text-muted-foreground">
                            {dimension.comment}
                          </p>
                        </div>
                      ))
                    ) : (
                      <pre className="m-0 overflow-auto whitespace-pre-wrap break-all font-mono text-xs">
                        {JSON.stringify(review, null, 2)}
                      </pre>
                    )}
                  </>
                ) : (
                  <pre className="m-0 overflow-auto whitespace-pre-wrap break-all font-mono text-xs">
                    {JSON.stringify(review, null, 2)}
                  </pre>
                )}
              </section>
            )}
            {!!batchDetail.topics?.length && (
              <section
                aria-label="提炼话题"
                className="grid gap-3 border-0 border-t border-solid border-border pt-4"
              >
                <h3 className="m-0 text-base font-medium">
                  提炼话题 · {batchDetail.topics.length}
                </h3>
                {batchDetail.topics.map((topic, index) => (
                  <div key={index} className="grid gap-1">
                    <span>{topic.topic || "未命名话题"}</span>
                    {topic.detail && (
                      <p className="m-0 whitespace-pre-wrap text-muted-foreground">
                        {topic.detail}
                      </p>
                    )}
                    {!!(topic.contributors?.length || topic.contributor_ids?.length) && (
                      <p className="m-0 text-sm text-muted-foreground">
                        参与者：
                        {topic.contributors?.length
                          ? topic.contributors.join("、")
                          : topic.contributor_ids?.join("、")}
                      </p>
                    )}
                  </div>
                ))}
              </section>
            )}
            {!!batchDetail.golden_quotes?.length && (
              <section
                aria-label="精彩金句"
                className="grid gap-3 border-0 border-t border-solid border-border pt-4"
              >
                <h3 className="m-0 text-base font-medium">
                  精彩金句 · {batchDetail.golden_quotes.length}
                </h3>
                {batchDetail.golden_quotes.map((quote, index) => (
                  <blockquote
                    key={index}
                    className="m-0 border-0 border-l-2 border-solid border-warning/40 pl-3"
                  >
                    <p className="m-0 whitespace-pre-wrap">
                      {String(quote.content || "未记录内容")}
                    </p>
                    {quote.reason && (
                      <p className="m-0 mt-1 text-muted-foreground">{quote.reason}</p>
                    )}
                    {quote.sender && (
                      <footer className="mt-1 text-muted-foreground">{String(quote.sender)}</footer>
                    )}
                  </blockquote>
                ))}
              </section>
            )}
            <details>
              <summary className="w-fit cursor-pointer rounded-md py-1 focus-visible:outline-2 focus-visible:outline-ring">
                完整批次数据（JSON）
              </summary>
              <pre
                tabIndex={0}
                className="m-0 mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-muted p-3 font-mono text-xs focus-visible:outline-2 focus-visible:outline-ring"
              >
                {JSON.stringify(batchDetail, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <p role="status" className="text-muted-foreground">
            没有可显示的批次数据。
          </p>
        )}
        <div className="flex flex-wrap items-center justify-end gap-2 border-0 border-t border-solid border-border pt-3">
          <span role="status" className="mr-auto text-sm text-muted-foreground">
            {copyResult}
          </span>
          <Button
            variant="outline"
            disabled={loading || !!error || !batchDetail}
            onClick={async () => {
              const request = ++copyRequest.current;
              const copied = await copyToClipboard(JSON.stringify(batchDetail, null, 2));
              if (request === copyRequest.current)
                setCopyResult(copied ? "已复制完整 JSON" : "复制失败，可展开完整数据后手动复制。");
            }}
          >
            <IconCopy aria-hidden="true" />
            复制完整 JSON
          </Button>
          <Button onClick={onClose}>关闭详情</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
