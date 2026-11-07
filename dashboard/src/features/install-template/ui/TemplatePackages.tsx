import { useEffect, useRef, useState } from "react";
import { IconCopy, IconLoader2, IconRefresh, IconTrash } from "@tabler/icons-react";
import { templateCapabilities } from "../../../entities/report/model/templates";
import type { ManagedFileGroup } from "../../../entities/plugin-data/api/managedFilesApi";
import { formatBytes } from "../../../shared/lib/formatters";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { Button } from "../../../shared/ui/button";
import { SearchSelect } from "../../../shared/ui/search-select";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";
import { useTemplatePackages } from "../model/useTemplatePackages";

export function TemplatePackages({
  groups,
  directory,
  loading,
  busy,
  onSelect,
  onInstall,
  onCreate,
  onRefresh,
}: {
  groups: ManagedFileGroup[];
  directory: string;
  loading: boolean;
  busy: boolean;
  onSelect: (directory: string) => void;
  onInstall: () => void;
  onCreate: () => void;
  onRefresh: () => void;
}) {
  const vm = useTemplatePackages(groups, onRefresh);
  const selected = vm.rows.find((item) => item.directory === directory);
  const disabled = busy || !!vm.busy;
  const [confirmation, setConfirmation] = useState<ManagedFileGroup | null>(null);
  const [copyResult, setCopyResult] = useState("");
  const copyRequest = useRef(0);
  const currentDirectory = useRef(directory);
  currentDirectory.current = directory;
  useEffect(() => {
    const request = copyRequest;
    request.current++;
    setCopyResult("");
    return () => {
      request.current++;
    };
  }, [directory]);
  const options = vm.rows.map((item) => {
    const name =
      item.directory === "."
        ? "未归组文件"
        : item.template?.display_name || item.template?.label || item.directory;
    return {
      value: item.directory,
      label:
        name === item.directory || item.directory === "." ? name : `${name}（${item.directory}）`,
      searchText: `${name} ${item.directory} ${item.template?.desc || ""}`,
    };
  });
  return (
    <section
      className="grid min-w-0 gap-4"
      aria-label="自定义模板包"
      aria-busy={loading || vm.loading || disabled}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="min-w-0 flex-[1_1_300px]">
          <SearchSelect
            label="选择自定义模板"
            value={directory}
            options={[{ value: "", label: `全部模板（共 ${groups.length} 个）` }, ...options]}
            virtual
            disabled={disabled}
            onChange={onSelect}
          />
        </div>
        <Button disabled={disabled} onClick={onInstall}>
          安装模板包
        </Button>
        {!directory && (
          <Button variant="outline" disabled={disabled} onClick={onCreate}>
            新建模板源码
          </Button>
        )}
        <Button
          variant="outline"
          disabled={disabled || loading || vm.loading}
          onClick={() => {
            onRefresh();
            void vm.refresh();
          }}
        >
          <IconRefresh aria-hidden="true" className={loading || vm.loading ? "animate-spin" : ""} />
          刷新模板
        </Button>
      </div>
      {(loading || vm.loading) && (
        <p role="status" className="m-0 text-sm text-muted-foreground">
          正在读取模板信息…
        </p>
      )}
      {vm.error && (
        <div role="alert" className="rounded-xl bg-warning/10 p-3 text-sm text-warning">
          {vm.error}。目录与文件仍可管理，请刷新模板信息后确认渲染能力。
        </div>
      )}
      {selected ? (
        <>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <code className="min-w-0 break-all text-sm">
              {directory === "." ? "模板分区根目录中的零散文件" : `${directory}/`}
            </code>
            <Button
              variant="ghost"
              size="sm"
              aria-label="复制模板目录"
              onClick={async () => {
                const request = ++copyRequest.current;
                const copied = await copyToClipboard(
                  directory === "." ? "模板分区根目录中的零散文件" : `${directory}/`,
                );
                if (request === copyRequest.current)
                  setCopyResult(copied ? "目录已复制" : "复制失败，可选择目录文字复制。");
              }}
            >
              <IconCopy aria-hidden="true" />
              复制目录
            </Button>
            {selected.template &&
              templateCapabilities(selected.template).map((label) => (
                <span key={label} className="rounded-md bg-info/10 px-2 py-1 text-xs text-info">
                  {label}
                </span>
              ))}
            <span className="text-sm text-muted-foreground">
              {selected.count} 个文件 · {formatBytes(selected.size_bytes)}
            </span>
            {directory !== "." && (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:bg-destructive/10 sm:ml-auto"
                disabled={disabled}
                onClick={() => {
                  vm.clearActionError();
                  setConfirmation({
                    directory: selected.directory,
                    count: selected.count,
                    size_bytes: selected.size_bytes,
                  });
                }}
              >
                <IconTrash aria-hidden="true" />
                移除模板
              </Button>
            )}
            <span role="status" className="text-sm text-muted-foreground">
              {copyResult}
            </span>
          </div>
          {directory === "." ? (
            <p className="m-0 rounded-xl bg-info/10 p-3 text-sm text-info">
              这些文件不属于模板包，可在下方逐项或多选删除；不移除整个模板存储根目录。
            </p>
          ) : !selected.template && !vm.loading && !vm.error ? (
            <div role="status" className="rounded-xl bg-warning/10 p-3 text-sm text-warning">
              <p className="m-0">此目录缺少有效的渲染入口，仍可维护文件或整组移除。</p>
              <p className="mb-0 mt-1">
                检查 report.typ、image_template.html 或 html_template.html 等入口文件。
              </p>
            </div>
          ) : (
            selected.template?.desc && (
              <p className="m-0 text-sm text-muted-foreground">{selected.template.desc}</p>
            )
          )}
        </>
      ) : !loading && !groups.length ? (
        <p role="status" className="py-5 text-center text-sm text-muted-foreground">
          尚无自定义模板，可安装模板包或新建源码。
        </p>
      ) : (
        <p className="m-0 text-sm text-muted-foreground">
          选择一个模板，管理它的源码与素材；可直接搜索切换，内置模板不在此列表。
        </p>
      )}
      <Dialog
        open={!!confirmation}
        onOpenChange={(open) => {
          if (!open && !vm.busy) setConfirmation(null);
        }}
      >
        <DialogContent
          onEscapeKeyDown={(event) => {
            event.stopPropagation();
            if (vm.busy) event.preventDefault();
          }}
        >
          <DialogTitle>移除模板目录“{confirmation?.directory}”？</DialogTitle>
          <DialogDescription>
            将移除 {confirmation?.directory}/ 下全部 {confirmation?.count} 个文件及素材（
            {formatBytes(confirmation?.size_bytes || 0)}），包括当前筛选未显示的文件。
          </DialogDescription>
          <p className="m-0 text-sm text-warning">
            使用此模板的配置需重新选择；已生成的报告不受影响。需要保留的源码请先下载。
          </p>
          {vm.actionError && (
            <p role="alert" className="m-0 text-sm text-destructive">
              {vm.actionError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" disabled={!!vm.busy} onClick={() => setConfirmation(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={!!vm.busy}
              onClick={async () => {
                if (!confirmation) return;
                const target = confirmation.directory;
                if (await vm.uninstall(target)) {
                  setConfirmation(null);
                  if (currentDirectory.current === target) onSelect("");
                }
              }}
            >
              {vm.busy && <IconLoader2 aria-hidden="true" className="animate-spin" />}
              {vm.busy ? "正在移除…" : "移除整个模板"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
