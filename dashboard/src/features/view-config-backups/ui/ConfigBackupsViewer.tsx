import { LoadingState } from "@/shared/ui/loading-state";
import { IconHistory, IconRefresh } from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/shared/ui/dialog";
import { Pagination } from "@/shared/ui/pagination";
import { formatBytes } from "@/shared/lib/formatters";
import { useConfigBackups } from "@/features/view-config-backups/model/useConfigBackups";
import { JsonBackupTree } from "./JsonBackupTree";

const kindLabels = {
  upgrade: "升级配置备份",
  comic_migration: "漫画配置迁移备份",
  other: "其他 JSON 备份",
};

export function ConfigBackupsViewer() {
  const vm = useConfigBackups();
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="text-secondary-ink hover:bg-secondary-soft"
        onClick={vm.load}
      >
        <IconHistory aria-hidden="true" />
        查看备份
      </Button>
      <Dialog
        open={vm.open}
        onOpenChange={(open) => {
          if (!open) vm.close();
        }}
      >
        <DialogContent className="max-w-5xl">
          <DialogTitle>配置自动备份</DialogTitle>
          <DialogDescription>只读查看保存时的原始配置，不会覆盖当前配置。</DialogDescription>
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={vm.load} disabled={vm.loading}>
              <IconRefresh aria-hidden="true" className={vm.loading ? "animate-spin" : undefined} />
              刷新列表
            </Button>
          </div>
          {vm.error && (
            <p role="alert" className="m-0 text-sm text-destructive">
              {vm.error}
            </p>
          )}
          {vm.loading ? (
            <LoadingState className="py-6 text-center text-muted-foreground">
              正在读取备份列表…
            </LoadingState>
          ) : vm.items.length > 0 ? (
            <>
              <ul aria-label="配置备份" className="m-0 list-none divide-y divide-border p-0">
                {vm.visibleItems.map((item) => (
                  <li
                    key={item.filename}
                    className="flex flex-wrap items-start justify-between gap-3 py-3"
                  >
                    <div className="min-w-0 flex-1 space-y-2">
                      <p className="m-0 break-all font-mono text-sm">{item.filename}</p>
                      <dl className="m-0 flex flex-wrap gap-x-5 gap-y-2 text-xs">
                        <div>
                          <dt className="text-muted-foreground">类型</dt>
                          <dd className="m-0">{kindLabels[item.kind]}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">插件版本</dt>
                          <dd className="m-0">{item.plugin_version || "未记录"}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">保存时间</dt>
                          <dd className="m-0">
                            {item.saved_at ? item.saved_at.replace("T", " ") : "未记录"}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">大小</dt>
                          <dd className="m-0">{formatBytes(item.size_bytes)}</dd>
                        </div>
                      </dl>
                      {item.error && (
                        <p className="m-0 break-words text-sm text-destructive">
                          无法读取：{item.error}
                        </p>
                      )}
                    </div>
                    <Button
                      variant={vm.selectedFilename === item.filename ? "default" : "tonal"}
                      size="sm"
                      disabled={Boolean(item.error)}
                      aria-pressed={vm.selectedFilename === item.filename}
                      onClick={() => vm.select(item.filename)}
                    >
                      查看
                    </Button>
                  </li>
                ))}
              </ul>
              {vm.items.length > 5 && (
                <Pagination
                  page={vm.page}
                  pageSize={5}
                  pageSizes={[5]}
                  total={vm.items.length}
                  onChange={vm.setPage}
                />
              )}
            </>
          ) : !vm.error ? (
            <p role="status" className="py-6 text-center text-muted-foreground">
              暂无配置备份
            </p>
          ) : null}
          {vm.detailLoading && (
            <LoadingState className="text-sm text-muted-foreground">正在读取备份…</LoadingState>
          )}
          {vm.detailError && (
            <p role="alert" className="m-0 text-sm text-destructive">
              {vm.detailError}
            </p>
          )}
          {vm.detail && (
            <section
              aria-label="备份内容"
              className="min-w-0 space-y-3 border-t border-border pt-4"
            >
              <h3 className="m-0 break-all font-mono text-sm font-medium">
                {vm.detail.backup.filename}
              </h3>
              <div
                className="max-h-[50dvh] overflow-auto rounded-lg border border-border p-3"
                tabIndex={0}
                role="region"
                aria-label="原始配置键值"
              >
                <JsonBackupTree
                  key={vm.detail.backup.filename}
                  label="原始 JSON"
                  value={vm.detail.content}
                />
              </div>
            </section>
          )}
          {!vm.detail && !vm.detailLoading && !vm.detailError && vm.items.length > 0 && (
            <p className="m-0 text-sm text-muted-foreground">选择一份备份查看内容。</p>
          )}
          <div className="flex justify-end">
            <Button variant="outline" onClick={vm.close}>
              关闭备份
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
