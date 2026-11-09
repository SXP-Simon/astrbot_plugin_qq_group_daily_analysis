import { useRef } from "react";
import { IconBrandGithub, IconFileZip, IconDownload, IconX } from "@tabler/icons-react";
import type { TemplateInstallResult } from "@/entities/report/api/reportApi";
import { useTemplateInstall } from "@/features/install-template/model/useTemplateInstall";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/shared/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/shared/ui/tabs";
import { formatBytes } from "@/shared/lib/formatters";

interface TemplateInstallModalProps {
  open: boolean;
  onClose: () => void;
  onInstalled?: (result: TemplateInstallResult) => void;
}

export function TemplateInstallModal({ open, onClose, onInstalled }: TemplateInstallModalProps) {
  const vm = useTemplateInstall(open, onClose, onInstalled);
  const fileInput = useRef<HTMLInputElement>(null);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) vm.close();
      }}
    >
      <DialogContent
        className="max-w-2xl"
        onEscapeKeyDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          vm.close();
        }}
        onPointerDownOutside={(event) => {
          if (vm.busy) event.preventDefault();
        }}
      >
        <DialogTitle>安装自定义报告模板</DialogTitle>
        <DialogDescription>
          安装后即可在续跑和重绘中选择，无需重启。内置模板不能被覆盖。
        </DialogDescription>
        <Tabs value={vm.method} onValueChange={vm.setMethod}>
          <TabsList aria-label="模板安装方式">
            <TabsTrigger value="url" disabled={vm.busy}>
              <IconBrandGithub aria-hidden="true" />
              GitHub 链接
            </TabsTrigger>
            <TabsTrigger value="file" disabled={vm.busy}>
              <IconFileZip aria-hidden="true" />
              上传 ZIP
            </TabsTrigger>
          </TabsList>
          <TabsContent value={vm.method}>
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void vm.install();
              }}
            >
              {vm.method === "url" ? (
                <label className="grid gap-2 text-sm">
                  GitHub 仓库链接
                  <Input
                    type="url"
                    value={vm.url}
                    disabled={vm.busy}
                    onChange={(event) => vm.setUrl(event.target.value)}
                    placeholder="https://github.com/owner/repo"
                  />
                </label>
              ) : (
                <div
                  className="grid gap-2 rounded-xl border border-dashed border-border p-4"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (!vm.busy) vm.pickFile(event.dataTransfer.files[0] || null);
                  }}
                >
                  <div className="grid gap-2 text-sm">
                    <span>ZIP 压缩包</span>
                    <input
                      ref={fileInput}
                      aria-label="ZIP 压缩包"
                      className="sr-only"
                      tabIndex={-1}
                      type="file"
                      accept=".zip"
                      disabled={vm.busy}
                      onChange={(event) => {
                        vm.pickFile(event.target.files?.[0] || null);
                        event.target.value = "";
                      }}
                    />
                    <Button
                      variant="outline"
                      disabled={vm.busy}
                      onClick={() => fileInput.current?.click()}
                    >
                      选择 ZIP 文件
                    </Button>
                  </div>
                  <p className="m-0 text-sm text-muted-foreground">
                    可拖入单个 ZIP。请保留模板目录、组件与素材。
                  </p>
                  {vm.file && (
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="break-all">
                        {vm.file.name} · {formatBytes(vm.file.size)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="移除已选压缩包"
                        disabled={vm.busy}
                        onClick={() => vm.pickFile(null)}
                      >
                        <IconX aria-hidden="true" />
                      </Button>
                    </div>
                  )}
                </div>
              )}
              <label className="grid gap-2 text-sm">
                模板名（可选，留空自动推断）
                <Input
                  value={vm.method === "file" ? vm.names.file : vm.names.url}
                  disabled={vm.busy}
                  onChange={(event) => vm.setName(event.target.value)}
                  placeholder="gda_miku_dream"
                />
              </label>
              {vm.error && (
                <p
                  role="alert"
                  className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
                >
                  {vm.error}
                </p>
              )}
              <div className="flex justify-end gap-2">
                <Button variant="outline" disabled={vm.busy} onClick={vm.close}>
                  取消
                </Button>
                <Button type="submit" disabled={vm.busy}>
                  <IconDownload aria-hidden="true" />
                  {vm.busy ? "正在安装…" : vm.method === "file" ? "解压并安装" : "下载并安装"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
        <details className="border-t border-border pt-3 text-sm text-muted-foreground">
          <summary className="cursor-pointer text-foreground">模板要求与命名建议</summary>
          <div className="mt-3 grid gap-2 leading-relaxed">
            <p className="m-0">
              模板至少包含 <code>report.typ</code>（Typst）、<code>image_template.html</code>（HTML
              长图）或 <code>html_template.html</code>（HTML
              网页）中的一个入口，并保留相对导入的组件和资源。
            </p>
            <p className="m-0">
              模板名建议使用小写字母、数字、下划线，长度不超过 50，并添加前缀，例如{" "}
              <code>gda_miku_dream</code>。留空时从仓库或压缩包目录推断，自动去除归档的{" "}
              <code>-main</code>、<code>-master</code> 后缀。
            </p>
            <p className="m-0">
              根目录可放置 <code>template.json</code> 设置中文显示名，例如{" "}
              <code>{'{"name":"初音梦境"}'}</code>。内置示例位于{" "}
              <code>src/infrastructure/reporting/templates/scrapbook/</code>。
            </p>
            <a
              className="text-secondary-ink underline underline-offset-4"
              href="https://github.com/lingyun14beta/daily-analysis-report-theme"
              target="_blank"
              rel="noopener noreferrer"
            >
              查看模板示例仓库
            </a>
          </div>
        </details>
      </DialogContent>
    </Dialog>
  );
}
