import { useManagedFonts, type ManagedFontRow } from "../model/useManagedFonts";
import { useBrowserFontDownload } from "../model/useBrowserFontDownload";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { formatBytes } from "../../../shared/lib/formatters";
import { Button } from "../../../shared/ui/button";
import { ExternalLink } from "../../../shared/ui/ExternalLink";
import { FilePicker } from "../../../shared/ui/file-picker";

export function ManagedFontTable({
  vm,
  browserDownload,
  onReplace,
  onRemove,
}: {
  vm: ReturnType<typeof useManagedFonts>;
  browserDownload: ReturnType<typeof useBrowserFontDownload>;
  onReplace: (file: File, row: ManagedFontRow) => void;
  onRemove: (row: ManagedFontRow) => void;
}) {
  const locked = vm.busy || vm.loading;
  const installed = vm.pageRows.flatMap((row) => (row.file ? [row.name] : []));
  const selected = new Set(vm.selected);
  const allSelected = installed.length > 0 && installed.every((name) => selected.has(name));
  const themeName = (key: string) => KNOWN_TEMPLATES.find((item) => item.key === key)?.name || key;
  return (
    <div
      role="region"
      aria-label="字体列表"
      tabIndex={0}
      aria-busy={vm.loading}
      className="min-w-0 overflow-x-auto rounded-xl border border-border"
    >
      <table className="ui-data-table w-full min-w-[64rem] table-fixed border-collapse text-left text-sm">
        <colgroup>
          <col className="w-12" />
          <col className="w-56" />
          <col className="w-24" />
          <col className="w-24" />
          <col />
          <col className="w-44" />
          <col className="w-48" />
        </colgroup>
        <thead className="bg-muted/60 text-muted-foreground">
          <tr>
            <th className="p-3">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                aria-label="选择本页已安装字体"
                checked={allSelected}
                disabled={locked || !installed.length}
                onChange={(event) =>
                  vm.setSelected(
                    event.target.checked
                      ? [...new Set([...vm.selected, ...installed])].slice(0, 200)
                      : vm.selected.filter((name) => !installed.includes(name)),
                  )
                }
              />
            </th>
            {["字体文件", "安装状态", "大小", "依赖模板", "手动获取", "操作"].map((label) => (
              <th key={label} className="p-3 font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {vm.pageRows.map((row) => {
            const preset = vm.status?.presets?.find((item) => item.name === row.name);
            return (
              <tr
                key={row.name}
                aria-selected={selected.has(row.name)}
                className="border-t border-border align-top"
              >
                <td className="p-3">
                  <input
                    type="checkbox"
                    aria-label={`选择字体 ${row.name}`}
                    className="size-4 accent-primary"
                    checked={selected.has(row.name)}
                    disabled={
                      locked || !row.file || (selected.size >= 200 && !selected.has(row.name))
                    }
                    onChange={(event) =>
                      vm.setSelected(
                        event.target.checked
                          ? [...vm.selected, row.name]
                          : vm.selected.filter((name) => name !== row.name),
                      )
                    }
                  />
                </td>
                <td className="p-3 font-mono text-xs leading-relaxed [overflow-wrap:anywhere]">
                  {row.name}
                </td>
                <td className="p-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs ${row.file ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}
                  >
                    {row.file ? "已安装" : "缺失"}
                  </span>
                </td>
                <td className="p-3 font-mono text-xs">
                  {row.file ? formatBytes(row.file.size_bytes) : "—"}
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-1">
                    {!row.themes.length ? (
                      <span className="text-muted-foreground">自定义字体，供自定义模板使用</span>
                    ) : row.themes.length === vm.groups.length ? (
                      <span
                        title={row.themes.map(themeName).join("、")}
                        className="rounded-md bg-secondary-soft px-2 py-0.5 text-xs text-secondary-ink"
                      >
                        所有内置模板共享
                      </span>
                    ) : (
                      row.themes.map((key) => (
                        <span key={key} className="rounded-md bg-muted px-2 py-0.5 text-xs">
                          {themeName(key)}
                        </span>
                      ))
                    )}
                  </div>
                </td>
                <td className="p-3">
                  {preset ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <ExternalLink href={preset.upstream_url}>查看上游</ExternalLink>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-secondary-ink"
                        disabled={locked || browserDownload.running}
                        onClick={() => browserDownload.download(preset)}
                      >
                        直接下载
                      </Button>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {row.themes.length
                        ? "暂无来源链接，请刷新字体状态"
                        : "自定义字体请自行确认来源"}
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {row.file ? (
                      <>
                        <FilePicker
                          label={`选择替换文件 ${row.name}`}
                          accept=".ttf,.otf,.ttc"
                          disabled={locked}
                          onSelect={(file) => onReplace(file, row)}
                        >
                          替换
                        </FilePicker>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          disabled={locked}
                          onClick={() => onRemove(row)}
                        >
                          移除
                        </Button>
                      </>
                    ) : preset ? (
                      <FilePicker
                        label={`上传文件 ${row.name}`}
                        accept=".ttf,.otf,.ttc"
                        disabled={locked}
                        onSelect={(file) => void vm.upload(file, null, row.name)}
                      >
                        上传此字体
                      </FilePicker>
                    ) : (
                      <span className="text-xs text-muted-foreground">通过上方按钮补齐</span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
          {!vm.pageRows.length && (
            <tr>
              <td colSpan={7} className="p-6 text-center text-muted-foreground">
                {vm.loading
                  ? "正在读取字体…"
                  : vm.status
                    ? "没有符合条件的字体"
                    : "尚未读取到字体状态，请重试"}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
