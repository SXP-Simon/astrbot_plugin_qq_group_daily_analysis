import { useContext, useState } from "react";
import { IconRefresh, IconUpload } from "@tabler/icons-react";
import { FontDownloadProgress } from "./FontDownloadProgress";
import { FontUploadProgress } from "./FontUploadProgress";
import { ManagedFontTable } from "./ManagedFontTable";
import { FontMutationDialogs } from "./FontMutationDialogs";
import { useManagedFonts, type ManagedFontRow } from "../model/useManagedFonts";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import {
  DEFAULT_TEMPLATE_CDN_BASE_URL,
  TEMPLATE_CDN_PRESETS,
} from "../../../entities/config/model/renderingConfig";
import { FONT_DOWNLOAD_SOURCES } from "../../../entities/config/model/typstFonts";
import {
  FontManagementContext,
  type FontManagementSelection,
} from "../model/FontManagementContext";
import { useBrowserFontDownload } from "../model/useBrowserFontDownload";
import { BrowserFontDownloadProgress } from "./BrowserFontDownloadProgress";
import type { ManagedFile } from "../../../entities/plugin-data/api/managedFilesApi";
import { ExternalLink } from "../../../shared/ui/ExternalLink";
import { Alert } from "../../../shared/ui/alert";
import { Button } from "../../../shared/ui/button";
import { NativeSelect } from "../../../shared/ui/native-select";
import { FilePicker } from "../../../shared/ui/file-picker";
import { Input } from "../../../shared/ui/input";
import { Pagination } from "../../../shared/ui/pagination";

export function FontManager({
  onChanged,
  initialSelection,
}: {
  onChanged: () => void;
  initialSelection?: FontManagementSelection;
}) {
  const navigation = useContext(FontManagementContext);
  const vm = useManagedFonts(() => {
    onChanged();
    navigation?.changed();
  }, initialSelection);
  const browserDownload = useBrowserFontDownload();
  const [cdn, setCdn] = useState(initialSelection?.cdnBaseUrl || DEFAULT_TEMPLATE_CDN_BASE_URL);
  const [search, setSearch] = useState("");
  const [replacement, setReplacement] = useState<{ file: File; existing: ManagedFontRow } | null>(
    null,
  );
  const [removal, setRemoval] = useState<ManagedFile[] | null>(null);
  const disabled = vm.busy || vm.loading;
  const selectedFiles = vm.files.filter((file) => vm.selected.includes(file.name));
  const themeName = (key: string) => KNOWN_TEMPLATES.find((item) => item.key === key)?.name || key;
  return (
    <div className="min-w-0 space-y-4">
      <p className="m-0 text-sm text-muted-foreground">
        字体供本地 Typst 排版使用，与 HTML/T2I 网页字体独立。按模板补齐，共享字库只保存一份。
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="min-w-0 space-y-1 text-sm">
          管理字体的模板
          <NativeSelect
            aria-label="管理字体的模板"
            value={vm.theme}
            disabled={disabled}
            onChange={(event) => vm.selectTheme(event.target.value)}
          >
            <option value="__all__">全部预设与自定义字体</option>
            {vm.groups.map((group) => (
              <option key={group.theme} value={group.theme}>
                {themeName(group.theme)}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="min-w-0 space-y-1 text-sm">
          下载来源
          <NativeSelect
            aria-label="字体下载来源"
            value={vm.downloadQueue.source}
            disabled={disabled}
            onChange={(event) => vm.downloadQueue.setSource(event.target.value as "cdn" | "github")}
          >
            {FONT_DOWNLOAD_SOURCES.map((source) => (
              <option key={source.value} value={source.value}>
                {source.label}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="min-w-0 space-y-1 text-sm">
          CDN
          <NativeSelect
            aria-label="字体下载 CDN"
            value={cdn}
            disabled={disabled || vm.downloadQueue.source === "github"}
            onChange={(event) => setCdn(event.target.value)}
          >
            {!TEMPLATE_CDN_PRESETS.some((item) => item.value === cdn) && (
              <option value={cdn}>{cdn}</option>
            )}
            {TEMPLATE_CDN_PRESETS.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={disabled || !vm.status || !vm.missing}
          aria-busy={vm.downloadQueue.running}
          onClick={() => void vm.download(cdn)}
        >
          {vm.downloadQueue.running
            ? "正在补齐…"
            : vm.theme === "__all__"
              ? "补齐全部预设字体"
              : "补齐所选模板字体"}
        </Button>
        <Button
          variant="outline"
          disabled={disabled}
          aria-busy={vm.loading}
          onClick={() => void vm.refresh()}
        >
          <IconRefresh aria-hidden="true" className={vm.loading ? "animate-spin" : ""} />
          刷新字体状态
        </Button>
      </div>
      {vm.status && (
        <Alert
          variant={vm.missing ? "info" : "success"}
        >{`已安装 ${vm.installed} / ${vm.required} 个字体${vm.missing ? `，缺少 ${vm.missing} 个` : "，已就绪"}`}</Alert>
      )}
      <details className="text-sm text-muted-foreground">
        <summary className="cursor-pointer rounded-md py-1 focus-visible:outline-2 focus-visible:outline-ring">
          手动安装与字体说明
        </summary>
        <div className="space-y-2 pt-2">
          <p className="m-0">
            服务器下载不通时，可在下方「手动获取」下载，再「上传此字体」，自动使用预设文件名。替换或移除会影响所有依赖它的模板。
          </p>
          <p className="m-0">
            本地使用 TTF / OTF / TTC 字体。初音中文标题使用约 14 KB 的八字 TTF 子集；HTML/T2I
            网页端使用 WOFF2。
          </p>
          <p className="m-0">
            预设字体采用{" "}
            <ExternalLink href="https://openfontlicense.org/open-font-license-official-text/">
              SIL OFL 1.1
            </ExternalLink>
            ，保留版权和许可；初音标题字库为已更名的子集。自行上传字体前请确认授权，BlueArchive
            已改用 Noto Sans。
          </p>
        </div>
      </details>
      {(vm.downloadQueue.error || vm.downloadQueue.progress.total > 0) && (
        <FontDownloadProgress download={vm.downloadQueue} />
      )}
      <BrowserFontDownloadProgress download={browserDownload} />
      <FontUploadProgress upload={vm.fontUpload} />
      {vm.error && !replacement && !removal && <Alert variant="destructive">{vm.error}</Alert>}
      <div className="flex flex-wrap items-center gap-2">
        <form
          className="flex max-w-full items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            vm.searchFonts(search);
          }}
        >
          <Input
            aria-label="搜索字体"
            placeholder="搜索字体文件名"
            value={search}
            disabled={disabled}
            onChange={(event) => {
              setSearch(event.target.value);
              if (!event.target.value) vm.searchFonts("");
            }}
          />
          <Button variant="outline" size="sm" type="submit" disabled={disabled}>
            搜索
          </Button>
        </form>
        <div className="w-40">
          <NativeSelect
            aria-label="字体格式筛选"
            value={vm.format}
            disabled={disabled}
            onChange={(event) => vm.filterFormat(event.target.value)}
          >
            <option value="">全部字体格式</option>
            {["ttf", "otf", "ttc"].map((value) => (
              <option key={value} value={value}>
                {value.toUpperCase()}
              </option>
            ))}
          </NativeSelect>
        </div>
        <FilePicker
          label="选择上传字体"
          accept=".ttf,.otf,.ttc"
          disabled={disabled}
          onSelect={(file) => {
            const existing = vm.files.find((item) => item.name === file.name);
            if (existing)
              setReplacement({
                file,
                existing: {
                  name: existing.name,
                  file: existing,
                  themes: vm.groups
                    .filter((group) => group.required.includes(existing.name))
                    .map((group) => group.theme),
                },
              });
            else void vm.upload(file);
          }}
        >
          <IconUpload aria-hidden="true" />
          上传字体
        </FilePicker>
        <Button
          variant="ghost"
          className="text-destructive"
          disabled={disabled || !selectedFiles.length}
          onClick={() => setRemoval([...selectedFiles])}
        >
          移除所选（{selectedFiles.length}）
        </Button>
      </div>
      {vm.removed && (
        <Alert variant={vm.removed.failed.length ? "warning" : "success"}>
          <div>
            已移除 {vm.removed.deleted.length} 个字体，失败 {vm.removed.failed.length} 个
          </div>
          {vm.removed.failed.map((file) => (
            <div key={file.name}>
              {file.name}：{file.message}
            </div>
          ))}
        </Alert>
      )}
      <ManagedFontTable
        vm={vm}
        browserDownload={browserDownload}
        onReplace={(file, existing) => setReplacement({ file, existing })}
        onRemove={(row) => {
          if (row.file) setRemoval([row.file]);
        }}
      />
      <Pagination
        page={vm.page}
        pageSize={15}
        pageSizes={[15]}
        total={vm.rows.length}
        loading={vm.loading}
        disabled={vm.busy}
        onChange={(page) => vm.setPage(page)}
      />
      <p className="m-0 text-sm text-muted-foreground">
        已选 {vm.selected.length} 个字体（最多 200，支持跨页）。自定义字体也保存在插件 data
        目录；模板需填写字体内部的字体族名称，文件名不代表字体族。
      </p>
      <FontMutationDialogs
        vm={vm}
        replacement={replacement}
        removal={removal}
        onCloseReplacement={() => setReplacement(null)}
        onCloseRemoval={() => setRemoval(null)}
      />
    </div>
  );
}
