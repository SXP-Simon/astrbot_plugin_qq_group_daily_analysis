import { LoadingState } from "../../../shared/ui/loading-state";
import { useEffect, useRef, useState } from "react";
import {
  IconLoader2,
  IconRefresh,
  IconUpload,
  IconSearch,
  IconX,
  IconTrash,
} from "@tabler/icons-react";
import type {
  ManagedFile,
  ManagedPartition,
} from "../../../entities/plugin-data/api/managedFilesApi";
import { partitionPresentation } from "../../../entities/plugin-data/model/partitionPresentation";
import type { useManagedFiles } from "../model/useManagedFiles";
import type { useConfigFileReferences } from "../model/useConfigFileReferences";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { Pagination } from "../../../shared/ui/pagination";
import { ManagedFileDeleteDialog } from "./ManagedFileDeleteDialog";
import { ManagedFileTable } from "./ManagedFileTable";

export function ManagedFileList({
  vm,
  partition,
  references,
}: {
  vm: ReturnType<typeof useManagedFiles>;
  partition: ManagedPartition;
  references: ReturnType<typeof useConfigFileReferences>;
}) {
  const [draft, setDraft] = useState(vm.search);
  const [deletion, setDeletion] = useState<{
    partition: string;
    directory: string;
    files: ManagedFile[];
  } | null>(null);
  useEffect(() => {
    setDraft(vm.search);
  }, [vm.search, partition.key, vm.directory]);
  useEffect(() => {
    setDeletion(null);
  }, [partition.key, vm.directory]);
  const upload = useRef<HTMLInputElement>(null);
  const templatePrefix =
    partition.key === "custom_templates" && vm.directory && vm.directory !== "."
      ? `${vm.directory}/`
      : "";
  const fileAction = ["typst_assets", "preview_cache"].includes(partition.key) ? "清理" : "删除";
  const locked = vm.busy || vm.uploading;
  const currentDeletion =
    deletion?.partition === partition.key && deletion.directory === vm.directory ? deletion : null;
  return (
    <div className="grid min-w-0 gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <form
          className="flex min-w-0 flex-1 gap-2 sm:max-w-md"
          onSubmit={(event) => {
            event.preventDefault();
            vm.searchFiles(draft.trim());
          }}
        >
          <Input
            aria-label="搜索文件"
            type="search"
            placeholder="文件名或相对路径"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={locked}
          />
          <Button
            type="submit"
            variant="outline"
            size="icon"
            aria-label="搜索文件列表"
            disabled={locked}
          >
            <IconSearch aria-hidden="true" />
          </Button>
          {(draft || vm.search) && (
            <Button
              variant="ghost"
              size="icon"
              aria-label="清空文件搜索"
              disabled={locked}
              onClick={() => {
                setDraft("");
                vm.searchFiles("");
              }}
            >
              <IconX aria-hidden="true" />
            </Button>
          )}
        </form>
        <Button
          variant="outline"
          disabled={vm.loading || locked}
          onClick={() => {
            vm.clearSelection();
            void vm.load();
            void vm.refresh();
            void references.refresh();
          }}
        >
          <IconRefresh aria-hidden="true" />
          刷新列表
        </Button>
        {partition.writable && partition.key !== "config_files" && (
          <>
            <input
              ref={upload}
              type="file"
              className="sr-only"
              tabIndex={-1}
              aria-label="上传分区文件"
              disabled={locked}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void vm.prepareUpload(file);
              }}
            />
            <Button variant="outline" disabled={locked} onClick={() => upload.current?.click()}>
              {vm.uploading ? (
                <IconLoader2
                  aria-hidden="true"
                  className="animate-spin motion-reduce:animate-none"
                />
              ) : (
                <IconUpload aria-hidden="true" />
              )}
              {vm.uploading ? "正在读取文件…" : "上传文件"}
            </Button>
          </>
        )}
        {partition.key === "custom_templates" && (
          <Button
            variant="outline"
            disabled={locked}
            onClick={() => vm.setEditor({ name: templatePrefix, text: "" })}
          >
            新建源码
          </Button>
        )}
      </div>
      <div role="group" aria-label="文件类型筛选" className="flex flex-wrap gap-2">
        {[
          { value: "", label: "全部类型" },
          ...(partitionPresentation[partition.key]?.filters || []),
        ].map((filter) => (
          <Button
            key={filter.value}
            size="sm"
            variant={vm.extensions === filter.value ? "secondary" : "ghost"}
            aria-pressed={vm.extensions === filter.value}
            disabled={locked}
            onClick={() => vm.filterExtensions(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>
      {partition.deletable && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="mr-auto text-muted-foreground">
            已选 {vm.selected.length} 项（最多 200，支持跨页）
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={!vm.selected.length || locked}
            onClick={vm.clearSelection}
          >
            取消选择
          </Button>
          <Button
            variant="ghost"
            className="text-destructive"
            size="sm"
            disabled={!vm.selected.length || locked}
            onClick={() => {
              vm.clearActionError();
              setDeletion({
                partition: partition.key,
                directory: vm.directory,
                files: [...vm.selected],
              });
            }}
          >
            <IconTrash aria-hidden="true" />
            {fileAction}所选
          </Button>
        </div>
      )}
      {vm.busy && !vm.content && (
        <LoadingState className="text-sm text-muted-foreground">正在读取或处理文件…</LoadingState>
      )}
      {vm.deleteResult && (
        <div
          role="status"
          className={`rounded-xl p-3 text-sm ${vm.deleteResult.failed.length ? "bg-warning/10 text-warning" : "bg-success/10 text-success"}`}
        >
          {fileAction}成功 {vm.deleteResult.deleted.length} 项，失败 {vm.deleteResult.failed.length}{" "}
          项
          {vm.deleteResult.failed.map((file) => (
            <div key={file.name} className="break-all">
              {file.name}：{file.message}
            </div>
          ))}
        </div>
      )}
      {vm.loading && vm.files.length > 0 && (
        <p role="status" className="sr-only">
          正在刷新文件列表…
        </p>
      )}
      <ManagedFileTable
        vm={vm}
        partition={partition}
        references={references}
        templatePrefix={templatePrefix}
      />
      <Pagination
        page={vm.page}
        pageSize={20}
        pageSizes={[20]}
        total={vm.total}
        disabled={vm.loading || locked}
        onChange={(page) => vm.setPage(page)}
      />
      <ManagedFileDeleteDialog
        vm={vm}
        partition={partition}
        deletion={currentDeletion}
        onClose={() => setDeletion(null)}
        fileAction={fileAction}
      />
    </div>
  );
}
