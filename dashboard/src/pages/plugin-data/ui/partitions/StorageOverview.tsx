import { LoadingSkeleton, LoadingState } from "../../../../shared/ui/loading-state";
import { IconFolderOpen, IconRefresh } from "@tabler/icons-react";
import type { ManagedPartition } from "../../../../entities/plugin-data/api/managedFilesApi";
import { partitionPresentation } from "../../../../entities/plugin-data/model/partitionPresentation";
import type { useManagedFiles } from "../../../../features/manage-stored-files/model/useManagedFiles";
import { formatBytes } from "../../../../shared/lib/formatters";
import { Button } from "../../../../shared/ui/button";

export function StorageOverview({
  vm,
  onSelect,
}: {
  vm: Pick<
    ReturnType<typeof useManagedFiles>,
    "totals" | "partitions" | "error" | "overviewLoading" | "refresh"
  >;
  onSelect: (partition: ManagedPartition) => void;
}) {
  const { totalBytes, totalFiles, assetBytes } = vm.totals;
  const unavailable = !vm.partitions.length && (vm.overviewLoading || !!vm.error);
  return (
    <>
      <dl aria-busy={vm.overviewLoading} className="m-0 grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl bg-primary-soft p-4">
          <dt className="text-sm text-muted-foreground">插件文件占用</dt>
          <dd className="m-0 mt-1 text-2xl tabular-nums">
            {unavailable ? "—" : formatBytes(totalBytes)}
          </dd>
          {!unavailable && (
            <dd className="m-0 mt-1 text-sm text-muted-foreground">共 {totalFiles} 个文件</dd>
          )}
        </div>
        <div className="rounded-xl bg-muted/60 p-4">
          <dt className="text-sm text-muted-foreground">受管理分区</dt>
          <dd className="m-0 mt-1 text-2xl tabular-nums">
            {unavailable ? "—" : vm.partitions.length}
          </dd>
          <dd className="m-0 mt-1 text-sm text-muted-foreground">按用途提供管理入口</dd>
        </div>
        <div className="rounded-xl bg-secondary-soft p-4">
          <dt className="text-sm text-muted-foreground">字体与原始素材</dt>
          <dd className="m-0 mt-1 text-2xl tabular-nums">
            {unavailable ? "—" : formatBytes(assetBytes)}
          </dd>
          <dd className="m-0 mt-1 text-sm text-muted-foreground">可按模板补齐和替换</dd>
        </div>
      </dl>
      {vm.error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
        >
          <span className="break-words">{vm.error}</span>
          <Button variant="outline" disabled={vm.overviewLoading} onClick={() => void vm.refresh()}>
            重试
          </Button>
        </div>
      )}
      <section className="grid min-w-0 gap-3" aria-label="存储分区明细与管理">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="m-0 flex items-center gap-2 text-base font-medium">
            <IconFolderOpen size={18} aria-hidden="true" />
            存储分区明细与管理
          </h2>
          <Button variant="outline" disabled={vm.overviewLoading} onClick={() => void vm.refresh()}>
            <IconRefresh
              aria-hidden="true"
              className={vm.overviewLoading ? "animate-spin" : undefined}
            />
            刷新概览
          </Button>
        </div>
        {vm.overviewLoading && (
          <LoadingState
            skeleton={!vm.partitions.length}
            className="m-0 text-sm text-muted-foreground"
          >
            正在读取存储概览…
          </LoadingState>
        )}
        <div
          className="min-w-0 max-w-full overflow-x-auto rounded-xl border border-border"
          tabIndex={0}
          role="region"
          aria-label="存储分区表格，可横向滚动"
          aria-busy={vm.overviewLoading}
        >
          <table className="ui-data-table w-full min-w-[860px] border-collapse text-left text-sm">
            <thead className="bg-muted/60 text-muted-foreground">
              <tr>
                <th scope="col" className="p-3 font-medium">
                  数据分区
                </th>
                <th scope="col" className="p-3 text-right font-medium">
                  文件
                </th>
                <th scope="col" className="p-3 text-right font-medium">
                  占用空间
                </th>
                <th scope="col" className="w-28 p-3 font-medium">
                  占比
                </th>
                <th scope="col" className="p-3 font-medium">
                  分区用途与能力
                </th>
                <th scope="col" className="p-3 font-medium">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {vm.overviewLoading && !vm.partitions.length && (
                <tr aria-hidden="true">
                  <td colSpan={6} className="p-4">
                    <LoadingSkeleton />
                  </td>
                </tr>
              )}
              {vm.partitions.map((item) => {
                const ratio =
                  totalBytes > 0
                    ? Math.min(100, Math.max(0, (item.size_bytes / totalBytes) * 100))
                    : 0;
                return (
                  <tr key={item.key} className="border-t border-border">
                    <th scope="row" className="w-56 p-3 font-normal">
                      <span className="font-medium">{item.name}</span>
                      <code className="mt-1 block max-w-56 break-all text-xs text-muted-foreground">
                        {item.directory}
                      </code>
                    </th>
                    <td className="p-3 text-right tabular-nums">{item.count}</td>
                    <td className="whitespace-nowrap p-3 text-right tabular-nums text-secondary-ink">
                      {formatBytes(item.size_bytes)}
                    </td>
                    <td className="p-3">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {ratio > 0 && ratio < 1 ? "< 1" : Math.round(ratio)}%
                      </span>
                      <div
                        className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted"
                        role="meter"
                        aria-label={`${item.name}占总空间`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={ratio}
                        aria-valuetext={`${Number(ratio.toFixed(1))}%`}
                      >
                        <div
                          className="h-full rounded-full bg-secondary-ink/50"
                          style={{ width: `${ratio}%` }}
                        />
                      </div>
                    </td>
                    <td className="p-3">
                      <p className="m-0">{item.description}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {partitionPresentation[item.key]?.capabilities.map((label) => (
                          <span
                            key={label}
                            className={`rounded-md px-2 py-0.5 text-xs ${["custom_templates", "config_files", "typst_fonts", "template_resources"].includes(item.key) ? "bg-primary-soft text-primary-ink" : "bg-secondary-soft text-secondary-ink"}`}
                          >
                            {label}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-3">
                      <Button variant="tonal" size="sm" onClick={() => onSelect(item)}>
                        管理
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!vm.partitions.length && !vm.overviewLoading && !vm.error && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">暂无受管理分区</p>
          )}
        </div>
      </section>
    </>
  );
}
