import { IconX } from "@tabler/icons-react";
import { Alert } from "../../../../shared/ui/alert";
import { Button } from "../../../../shared/ui/button";
import { CopyButton } from "../../../../shared/ui/copy-button";
import { Dialog, DialogClose, DialogContent, DialogTitle } from "../../../../shared/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../../../shared/ui/tabs";
import { useState, type ReactNode } from "react";
import { usePartitionManager } from "../../model/usePartitionManager";
import { StoredRecordsTab } from "../StoredRecordsTab";
import { ManagedFileList } from "../../../../features/manage-stored-files/ui/ManagedFileList";
import { FileContentDialog } from "../../../../features/manage-stored-files/ui/FileContentDialog";
import { FileEditorDialog } from "../../../../features/manage-stored-files/ui/FileEditorDialog";
import { FontManager } from "../../../../features/manage-typst-fonts/ui/FontManager";
import { TemplatePackages } from "../../../../features/install-template/ui/TemplatePackages";
import { TemplateInstallModal } from "../../../../features/install-template/ui/TemplateInstallModal";
import { TemplateResources } from "../../../../features/manage-template-resources/ui/TemplateResources";
import { ConfigBackupsViewer } from "../../../../features/view-config-backups/ui/ConfigBackupsViewer";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../../entities/config/model/renderingConfig";

export function ManagedPartitionDrawer({
  manager,
}: {
  manager: ReturnType<typeof usePartitionManager>;
}) {
  const [resourceVersion, setResourceVersion] = useState(0);
  const { files: vm, partition, references, links } = manager;
  const specializedManagers: Record<string, ReactNode> = {
    typst_fonts: (
      <FontManager
        key={manager.fontSelection?.sequence || 0}
        initialSelection={manager.fontSelection || undefined}
        onChanged={manager.refresh}
      />
    ),
    avatar_storage: <StoredRecordsTab onlyKind="avatar" />,
  };
  return (
    <Dialog
      open={!!vm.partition}
      onOpenChange={(open) => {
        if (!open) manager.closePartition();
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="block inset-y-0 left-auto right-0 top-0 h-dvh max-h-dvh w-[min(1100px,96vw)] max-w-none translate-x-0 translate-y-0 gap-0 rounded-l-2xl rounded-r-none p-0"
        aria-describedby={undefined}
      >
        <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-4">
          <DialogTitle>{vm.partition?.name || "存储分区"}</DialogTitle>
          <DialogClose asChild>
            <Button variant="ghost" size="icon" aria-label="关闭分区">
              <IconX aria-hidden="true" />
            </Button>
          </DialogClose>
        </header>
        <div className="min-w-0 space-y-4 p-6">
          {partition && (
            <div className="min-w-0 space-y-4">
              <dl className="m-0 grid min-w-0 gap-2 text-sm">
                <dt className="text-muted-foreground">存储目录</dt>
                <dd className="m-0 flex min-w-0 items-start gap-2">
                  <code className="min-w-0 flex-1 break-all text-xs">{partition.directory}</code>
                  <CopyButton text={partition.directory} label="复制存储目录" />
                </dd>
                <dt className="text-muted-foreground">用途</dt>
                <dd className="m-0">{partition.description}</dd>
              </dl>
              <Alert variant={partition.deletable ? "warning" : "info"}>{partition.impact}</Alert>
              {vm.listError && (
                <Alert variant="destructive">
                  <div>{vm.listError}</div>
                  <Button variant="outline" size="sm" onClick={() => void vm.load()}>
                    重试列表
                  </Button>
                </Alert>
              )}
              {partition.key === "config_files" && (
                <>
                  <p className="m-0 text-sm text-muted-foreground">
                    新增图片需在配置中心选择对应字段；这里可预览、同名替换、复制引用路径与清理文件。下列引用来自当前已保存的插件配置。
                  </p>
                  {references.error && (
                    <Alert variant="warning">
                      <div>{references.error}</div>
                      <p className="m-0">无法确认引用关系，请先刷新或打开配置中心检查。</p>
                      <Button variant="outline" size="sm" onClick={() => void references.refresh()}>
                        重新检查
                      </Button>
                    </Alert>
                  )}
                </>
              )}
              {(links.length > 0 || partition.key === "config_backups") && (
                <div className="flex flex-wrap gap-2">
                  {links.map((link) => (
                    <Button
                      key={`${link.kind}:${link.destination}`}
                      onClick={() => manager.navigate(link)}
                    >
                      {link.label}
                    </Button>
                  ))}
                  {partition.key === "config_backups" && <ConfigBackupsViewer />}
                </div>
              )}
              {partition.key === "typst_fonts" && manager.fontSelection && (
                <Button
                  onClick={() =>
                    manager.navigate({
                      kind: "page",
                      destination: "config",
                      label: "返回 Typst 方案",
                    })
                  }
                >
                  返回 Typst 方案
                </Button>
              )}
              {partition.key === "template_resources" && manager.resourceSelection && (
                <Button
                  onClick={() =>
                    manager.navigate({
                      kind: "page",
                      destination: "config",
                      label: "返回 Typst 方案",
                    })
                  }
                >
                  返回 Typst 方案
                </Button>
              )}
              {partition.key === "custom_templates" && (
                <TemplatePackages
                  groups={vm.groups}
                  directory={vm.directory}
                  loading={vm.loading}
                  busy={vm.busy}
                  onSelect={vm.selectDirectory}
                  onInstall={() => manager.setInstalling(true)}
                  onCreate={() => vm.setEditor({ name: "", text: "" })}
                  onRefresh={manager.refresh}
                />
              )}
              {specializedManagers[partition.key] ||
                (partition.key === "custom_templates" && !vm.directory ? null : (
                  <Tabs
                    key={`${partition.key}:${vm.directory}:${manager.resourceSelection?.sequence || 0}`}
                    defaultValue={partition.key === "template_resources" ? "download" : "files"}
                    onValueChange={(key) => {
                      manager.refresh();
                      if (key === "download") setResourceVersion((value) => value + 1);
                    }}
                  >
                    <TabsList aria-label="分区管理方式" className="max-w-full overflow-x-auto">
                      {partition.key === "template_resources" && (
                        <TabsTrigger value="download">主题素材管理</TabsTrigger>
                      )}
                      <TabsTrigger value="files">
                        {partition.key === "template_resources"
                          ? "本地素材与替换"
                          : partition.key === "state"
                            ? "数据库与状态占用"
                            : partition.key === "typst_jobs"
                              ? "只读诊断文件"
                              : "文件列表"}
                      </TabsTrigger>
                    </TabsList>
                    {partition.key === "template_resources" && (
                      <TabsContent value="download">
                        <TemplateResources
                          refreshVersion={resourceVersion + partition.count + partition.size_bytes}
                          cdnBaseUrl={
                            manager.resourceSelection?.cdnBaseUrl || DEFAULT_TEMPLATE_CDN_BASE_URL
                          }
                          initialTheme={manager.resourceSelection?.theme}
                          onThemeChange={(theme) => vm.searchFiles(`${theme}/`)}
                          onUpload={(file, name) => void vm.prepareUpload(file, false, name)}
                          onChanged={manager.refresh}
                        />
                      </TabsContent>
                    )}
                    <TabsContent value="files">
                      <ManagedFileList vm={vm} partition={partition} references={references} />
                    </TabsContent>
                  </Tabs>
                ))}
            </div>
          )}
          {partition?.key !== "typst_fonts" && (
            <FileContentDialog
              vm={vm}
              editor={vm.editor}
              setEditor={vm.setEditor}
              references={
                partition?.key === "config_files" && vm.content
                  ? references.references.get(vm.content.name)
                  : undefined
              }
            />
          )}
          {!vm.content && <FileEditorDialog vm={vm} editor={vm.editor} setEditor={vm.setEditor} />}
          <TemplateInstallModal
            open={manager.installing}
            onClose={() => manager.setInstalling(false)}
            onInstalled={(result) => {
              vm.selectDirectory(result.name);
              void vm.refresh();
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
