import { LoadingState } from "../../../shared/ui/loading-state";
import { useContext, useEffect, useId, useState } from "react";
import { IconRefresh, IconUpload } from "@tabler/icons-react";
import { TEMPLATE_CDN_PRESETS } from "../../../entities/config/model/renderingConfig";
import { KNOWN_TEMPLATES } from "../../../entities/report/model/templates";
import { useTemplateResources } from "../model/useTemplateResources";
import { ResourceManagementContext } from "../model/ResourceManagementContext";
import { Alert } from "../../../shared/ui/alert";
import { Button } from "../../../shared/ui/button";
import { CopyButton } from "../../../shared/ui/copy-button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";
import { Progress } from "../../../shared/ui/progress";

export function TemplateResources({
  cdnBaseUrl,
  onChanged,
  refreshVersion = 0,
  initialTheme,
  onUpload,
  onThemeChange,
}: {
  cdnBaseUrl: string;
  onChanged?: () => void;
  refreshVersion?: number;
  initialTheme?: string;
  onUpload?: (file: File, name: string) => void;
  onThemeChange?: (theme: string) => void;
}) {
  const navigation = useContext(ResourceManagementContext);
  const [cdn, setCdn] = useState(cdnBaseUrl);
  const [theme, setTheme] = useState(initialTheme || "HatsuneMiku");
  const presetsId = useId();
  useEffect(() => setCdn(cdnBaseUrl), [cdnBaseUrl]);
  const vm = useTemplateResources(cdn, refreshVersion + (navigation?.version || 0));
  const missing =
    vm.status?.groups.flatMap((group) => group.files).filter((file) => !file.available).length ?? 0;
  const group = vm.status?.groups.find((item) => item.theme === theme);
  const ready = group?.files.filter((file) => file.available).length || 0;
  const themeName = KNOWN_TEMPLATES.find((item) => item.key === theme)?.name || theme;
  return (
    <section className="mt-4 grid min-w-0 gap-4" aria-label="模板原始素材">
      <h3 className="m-0 text-base font-medium">模板原始素材</h3>
      <p className="m-0 text-sm text-muted-foreground">
        将主题图标和角色原图下载到插件，已有素材会复用；缺图时使用渲染方案的 CDN。
      </p>
      <div className="flex min-w-0 flex-wrap items-end gap-3">
        <label className="grid min-w-0 flex-[1_1_260px] gap-1 text-sm">
          模板
          <NativeSelect
            aria-label="管理素材的模板"
            value={theme}
            disabled={vm.running || !vm.status?.groups.length}
            onChange={(event) => {
              setTheme(event.target.value);
              onThemeChange?.(event.target.value);
            }}
          >
            {!vm.status?.groups.some((item) => item.theme === theme) && (
              <option value={theme}>{themeName}</option>
            )}
            {vm.status?.groups.map((item) => (
              <option key={item.theme} value={item.theme}>
                {KNOWN_TEMPLATES.find((template) => template.key === item.theme)?.name ||
                  item.theme}
              </option>
            ))}
          </NativeSelect>
        </label>
        {navigation && !onUpload && (
          <Button
            variant="outline"
            disabled={vm.running}
            onClick={() => navigation.open({ theme, cdnBaseUrl: cdn })}
          >
            管理 / 上传模板素材
          </Button>
        )}
      </div>
      <label className="grid min-w-0 gap-1 text-sm">
        素材下载 CDN
        <Input
          aria-label="素材下载 CDN"
          list={presetsId}
          value={cdn}
          disabled={vm.running}
          onChange={(event) => setCdn(event.target.value)}
          placeholder="选择预设或输入自定义根地址"
        />
      </label>
      <datalist id={presetsId}>
        {TEMPLATE_CDN_PRESETS.map((preset) => (
          <option key={preset.value} value={preset.value}>
            {preset.label}
          </option>
        ))}
      </datalist>
      <p className="m-0 text-sm text-muted-foreground">
        这里的 CDN 仅用于本次下载，不会修改渲染方案。
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          disabled={vm.running || vm.loading || !missing}
          onClick={() =>
            void vm.download().then((changed) => {
              if (changed) onChanged?.();
            })
          }
        >
          下载全部缺失素材
        </Button>
        {vm.running && (
          <Button variant="outline" disabled={vm.cancelling} onClick={() => void vm.cancel()}>
            {vm.cancelling ? "正在取消…" : "取消下载"}
          </Button>
        )}
        <Button
          variant="outline"
          disabled={vm.running || vm.loading}
          onClick={() => void vm.refresh()}
        >
          <IconRefresh aria-hidden="true" className={vm.loading ? "animate-spin" : ""} />
          刷新素材状态
        </Button>
      </div>
      {vm.loading && (
        <LoadingState className="m-0 text-sm text-muted-foreground">正在读取素材状态…</LoadingState>
      )}
      {vm.progress.total > 0 && (
        <>
          <Progress
            label="模板素材处理进度"
            value={(vm.progress.done / vm.progress.total) * 100}
            variant={
              vm.cancelled
                ? "info"
                : vm.progress.failed.length
                  ? "warning"
                  : vm.running
                    ? "default"
                    : "success"
            }
          />
          <p className="m-0 text-sm">
            完成 {vm.progress.done}/{vm.progress.total}，成功{" "}
            {vm.progress.done - vm.progress.failed.length}，失败 {vm.progress.failed.length}
          </p>
          {!vm.running && vm.cancelled && (
            <Alert>下载已取消，已完成的素材会保留；再次下载仅补齐缺失文件。</Alert>
          )}
          {!vm.running && !vm.cancelled && (
            <Alert variant={vm.progress.failed.length ? "warning" : "success"}>
              {vm.progress.failed.length
                ? "部分素材未下载成功，可更换 CDN 后重试；已有文件会跳过"
                : "本轮素材下载完成"}
            </Alert>
          )}
        </>
      )}
      {vm.error && <Alert variant="destructive">{vm.error}</Alert>}
      {vm.progress.failed.length > 0 && (
        <ul
          aria-label="未完成的素材"
          className="m-0 max-h-52 list-none overflow-auto p-0 text-sm text-destructive"
        >
          {vm.progress.failed.map((file) => (
            <li key={file.name} className="break-words border-b border-border py-2 last:border-0">
              {file.name}：{file.message}
            </li>
          ))}
        </ul>
      )}
      {vm.status && (
        <>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <code className="min-w-0 break-all text-xs text-muted-foreground">
              {vm.status.directory}
            </code>
            <CopyButton text={vm.status.directory} label="复制素材目录">
              复制目录
            </CopyButton>
          </div>
          {group && (
            <div className="grid min-w-0 gap-3 border-t border-border pt-4">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="font-medium">{themeName}</span>
                <span
                  className={`rounded-md px-2 py-1 text-xs ${ready === group.files.length ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}
                >
                  {group.files.length ? `${ready}/${group.files.length} 已就绪` : "无需外置素材"}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="sm:ml-auto"
                  disabled={vm.running || vm.loading || ready === group.files.length}
                  onClick={() =>
                    void vm.download(group.theme).then((changed) => {
                      if (changed) onChanged?.();
                    })
                  }
                >
                  下载 {group.theme} 素材
                </Button>
              </div>
              {group.files.length > 0 && (
                <details>
                  <summary className="cursor-pointer rounded-lg py-1 text-sm focus-visible:outline-2 focus-visible:outline-ring">
                    素材文件与状态
                  </summary>
                  <ul className="m-0 list-none divide-y divide-border p-0">
                    {group.files.map((file) => (
                      <li
                        key={file.name}
                        className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] items-start gap-2 py-2 text-sm sm:grid-cols-[auto_minmax(0,1fr)_auto]"
                      >
                        <span
                          className={`rounded-md px-2 py-1 text-xs ${file.available ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}
                        >
                          {file.available ? "已就绪" : "缺失"}
                        </span>
                        <code className="min-w-0 break-all py-1 text-xs">{file.name}</code>
                        <div className="col-span-2 flex flex-wrap items-center justify-end gap-2 sm:col-span-1">
                          <CopyButton text={file.name} label={`复制素材名称 ${file.name}`} />
                          {onUpload && (
                            <label
                              className={`inline-flex h-8 items-center gap-2 rounded-xl border border-input px-3 text-sm focus-within:ring-2 focus-within:ring-ring ${vm.running ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-accent"}`}
                            >
                              <IconUpload aria-hidden="true" className="size-4" />
                              上传 / 替换此素材
                              <input
                                type="file"
                                aria-label={`上传或替换 ${file.name}`}
                                accept="image/*,.svg"
                                className="sr-only"
                                disabled={vm.running}
                                onChange={(event) => {
                                  const chosen = event.target.files?.[0];
                                  event.target.value = "";
                                  if (chosen) onUpload(chosen, file.name);
                                }}
                              />
                            </label>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
          <p className="m-0 text-sm text-muted-foreground">
            就绪状态也可能包含插件仓库自带的素材；本地素材列表只显示插件 data 目录中的文件。Emoji
            使用字体，无需单独下载图片。
          </p>
        </>
      )}
    </section>
  );
}
