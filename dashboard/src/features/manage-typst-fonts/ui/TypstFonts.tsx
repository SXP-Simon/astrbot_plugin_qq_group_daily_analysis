import { useContext, useState } from "react";
import { FontDownloadProgress } from "./FontDownloadProgress";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useTypstFonts } from "../model/useTypstFonts";
import { FONT_DOWNLOAD_SOURCES } from "../../../entities/config/model/typstFonts";
import { FontManagementContext } from "../model/FontManagementContext";
import { ExternalLink } from "../../../shared/ui/ExternalLink";
import { Alert } from "../../../shared/ui/alert";
import { Button } from "../../../shared/ui/button";
import { CopyButton } from "../../../shared/ui/copy-button";
import { NativeSelect } from "../../../shared/ui/native-select";

export function TypstFonts({ cdnBaseUrl }: { cdnBaseUrl: string }) {
  const navigation = useContext(FontManagementContext);
  const vm = useTypstFonts(cdnBaseUrl, navigation?.version);
  const [theme, setTheme] = useState("HatsuneMiku");
  const group = vm.status?.groups?.find((item) => item.theme === theme);
  return (
    <section className="mt-3 min-w-0 space-y-3" aria-label="Typst 字体">
      <h3 className="m-0 text-base font-medium">Typst 字体</h3>
      <p className="m-0 text-sm text-muted-foreground">
        供插件本地 Typst 排版使用，不影响 HTML / T2I 的网页字体。按模板补齐，共享字体只保存一份。
      </p>
      <NativeSelect
        aria-label="字体模板"
        value={theme}
        disabled={vm.loading || !vm.status?.groups?.length}
        onChange={(event) => setTheme(event.target.value)}
      >
        {vm.status?.groups?.map((item) => (
          <option key={item.theme} value={item.theme}>
            {KNOWN_TEMPLATES.find((template) => template.key === item.theme)?.name || item.theme}
          </option>
        ))}
      </NativeSelect>
      {vm.status && (
        <>
          <Alert variant={group?.ready ? "success" : "info"}>
            {group
              ? group.ready
                ? "所选模板字体已就绪"
                : `所选模板还需下载 ${group.missing.length} / ${group.required.length} 个字体文件`
              : vm.status.ready
                ? "全部预设字体已就绪"
                : `全部预设还缺 ${vm.status.missing.length} 个字体文件`}
          </Alert>
          <div className="flex min-w-0 items-start gap-2">
            <code className="min-w-0 flex-1 break-all text-xs text-muted-foreground">
              {vm.status.directory}
            </code>
            <CopyButton text={vm.status.directory} label="复制字体目录" />
          </div>
          <div className="flex flex-wrap gap-1">
            {group?.required.map((file) => (
              <span
                key={file}
                className={`rounded-md px-2 py-1 font-mono text-xs ${group.missing.includes(file) ? "bg-muted text-muted-foreground" : "bg-success/10 text-success"}`}
              >
                {file}
              </span>
            ))}
          </div>
        </>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-80 max-w-full">
          <NativeSelect
            aria-label="字体下载来源"
            value={vm.downloadQueue.source}
            disabled={vm.loading}
            onChange={(event) => vm.downloadQueue.setSource(event.target.value as "cdn" | "github")}
          >
            {FONT_DOWNLOAD_SOURCES.map((source) => (
              <option key={source.value} value={source.value}>
                {source.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button
          variant="outline"
          disabled={vm.loading || !group || group.ready}
          aria-busy={vm.operation === "selected"}
          onClick={() => void vm.run(true, theme)}
        >
          下载所选模板字体
        </Button>
        <Button
          variant="outline"
          disabled={vm.loading || !vm.status || vm.status.ready}
          aria-busy={vm.operation === "all"}
          onClick={() => void vm.run(true)}
        >
          下载全部预设字体
        </Button>
        <Button
          variant="ghost"
          disabled={vm.loading}
          aria-busy={vm.operation === "refresh"}
          onClick={() => void vm.run(false)}
        >
          刷新字体状态
        </Button>
        {navigation && (
          <Button
            variant="outline"
            disabled={vm.loading}
            onClick={() => navigation.open({ theme, cdnBaseUrl, source: vm.downloadQueue.source })}
          >
            管理 / 上传字体
          </Button>
        )}
      </div>
      <details className="text-sm text-muted-foreground">
        <summary className="cursor-pointer rounded-md py-1 focus-visible:outline-2 focus-visible:outline-ring">
          下载来源与字体许可
        </summary>
        <div className="space-y-2 pt-2">
          <p className="m-0">
            初音中文标题使用约 14 KB 的八字 TTF 子集；网页端仍使用
            WOFF2。预设包含简体、繁体、日文、Emoji 和符号等共享基础字库，保存在本插件 data 目录。
          </p>
          <p className="m-0">
            CDN 优先模式下，大字库（含 ATRI 文楷）仍从固定 GitHub Raw 地址下载；也可选择全部字体走
            Raw，绕过镜像 CDN 的体积限制。服务器无法访问 Raw 时需检查网络或代理，更换 CDN
            不会改变直连地址。CDN 下载失败自动尝试 Raw 备用源，重试只补缺失文件。
          </p>
          <p className="m-0">
            下载失败可打开「管理 / 上传字体」，进入「数据 → 存储空间概览 → Typst
            字体」。从对应行查看上游或直接下载，再「上传此字体」，自动按预设命名。
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
      {vm.error && <Alert variant="destructive">{vm.error}</Alert>}
    </section>
  );
}
