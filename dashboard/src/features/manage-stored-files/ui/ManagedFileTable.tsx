import { IconFile, IconCopy } from "@tabler/icons-react";
import { toast } from "sonner";
import type { ManagedPartition } from "../../../entities/plugin-data/api/managedFilesApi";
import { partitionPresentation } from "../../../entities/plugin-data/model/partitionPresentation";
import { formatBytes } from "../../../shared/lib/formatters";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { Button } from "../../../shared/ui/button";
import type { useManagedFiles } from "../model/useManagedFiles";
import type { useConfigFileReferences } from "../model/useConfigFileReferences";

export function ManagedFileTable({
  vm,
  partition,
  references,
  templatePrefix,
}: {
  vm: ReturnType<typeof useManagedFiles>;
  partition: ManagedPartition;
  references: ReturnType<typeof useConfigFileReferences>;
  templatePrefix: string;
}) {
  const selected = new Set(vm.selected.map((file) => file.name));
  const locked = vm.busy || vm.loading || vm.uploading;
  const allSelected = vm.files.length > 0 && vm.files.every((file) => selected.has(file.name));
  return (
    <div
      className="min-w-0 overflow-x-auto rounded-xl border border-border"
      role="region"
      aria-label="文件列表"
      tabIndex={0}
      aria-busy={vm.loading}
    >
      <table className="w-full min-w-[650px] text-left text-sm">
        <thead className="bg-muted/60 text-muted-foreground">
          <tr>
            {partition.deletable && (
              <th className="w-10 p-3">
                <input
                  type="checkbox"
                  aria-label="选择本页文件（最多 200）"
                  className="size-4 accent-primary"
                  checked={allSelected}
                  disabled={locked || !vm.files.length}
                  onChange={(event) =>
                    vm.selectFiles(
                      event.target.checked
                        ? [
                            ...selected,
                            ...vm.files
                              .map((file) => file.name)
                              .filter((name) => !selected.has(name)),
                          ].slice(0, 200)
                        : [...selected].filter(
                            (name) => !vm.files.some((file) => file.name === name),
                          ),
                    )
                  }
                />
              </th>
            )}
            <th className="p-3 font-medium">文件名</th>
            {partition.key === "config_files" && <th className="w-64 p-3 font-medium">配置引用</th>}
            <th className="w-28 p-3 font-medium">大小</th>
            <th className="w-44 p-3 font-medium">修改时间</th>
            <th className="w-40 p-3 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {vm.files.map((file) => (
            <tr key={file.name} className="border-t border-border hover:bg-muted/30">
              {partition.deletable && (
                <td className="p-3">
                  <input
                    type="checkbox"
                    aria-label={`选择文件 ${file.name}`}
                    className="size-4 accent-primary"
                    checked={selected.has(file.name)}
                    disabled={locked || (selected.size >= 200 && !selected.has(file.name))}
                    onChange={(event) =>
                      vm.selectFiles(
                        event.target.checked
                          ? [...selected, file.name]
                          : [...selected].filter((name) => name !== file.name),
                      )
                    }
                  />
                </td>
              )}
              <td className="max-w-md break-all p-3">
                <span className="flex items-start gap-2">
                  <IconFile aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-info" />
                  <span>
                    {templatePrefix && file.name.startsWith(templatePrefix)
                      ? file.name.slice(templatePrefix.length)
                      : file.name}
                  </span>
                </span>
              </td>
              {partition.key === "config_files" && (
                <td className="p-3">
                  <div className="flex items-center gap-1">
                    <code className="break-all text-xs">files/{file.name}</code>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`复制引用路径 files/${file.name}`}
                      onClick={async () => {
                        if (await copyToClipboard(`files/${file.name}`))
                          toast.success("引用路径已复制");
                        else toast.error("复制失败，请手动复制路径。");
                      }}
                    >
                      <IconCopy aria-hidden="true" />
                    </Button>
                  </div>
                  <p className="m-0 text-xs text-muted-foreground">
                    {references.loading
                      ? "正在检查引用…"
                      : references.error
                        ? "引用关系未确认"
                        : references.references.get(file.name)?.join("、") ||
                          "未在已保存配置中找到引用；自定义源码中的引用需自行确认。"}
                  </p>
                </td>
              )}
              <td className="whitespace-nowrap p-3 tabular-nums">{formatBytes(file.size_bytes)}</td>
              <td className="p-3 text-xs tabular-nums">
                {new Date(file.modified_at * 1000).toLocaleString()}
              </td>
              <td className="p-3">
                {file.downloadable ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={locked}
                    onClick={() =>
                      void (file.editable ||
                      /^(image\/|text\/|application\/json)/.test(file.media_type)
                        ? vm.inspect(file.name)
                        : vm.download(file.name))
                    }
                  >
                    {file.editable
                      ? "查看 / 编辑"
                      : /^(image\/|text\/html)/.test(file.media_type)
                        ? "预览 / 下载"
                        : /^(text\/|application\/json)/.test(file.media_type)
                          ? "查看内容 / 下载"
                          : "下载文件"}
                  </Button>
                ) : (
                  <span className="rounded-lg bg-muted px-2 py-1 text-xs text-muted-foreground">
                    由模块管理
                  </span>
                )}
              </td>
            </tr>
          ))}
          {!vm.files.length && !vm.loading && (
            <tr>
              <td
                colSpan={4 + Number(partition.deletable) + Number(partition.key === "config_files")}
                className="p-8 text-center text-muted-foreground"
              >
                {vm.search || vm.extensions
                  ? "没有匹配文件，请调整关键词或文件类型。"
                  : partitionPresentation[partition.key]?.empty || "暂无文件"}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
