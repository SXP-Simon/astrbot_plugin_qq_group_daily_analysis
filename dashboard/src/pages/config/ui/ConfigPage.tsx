import { useState } from "react";
import {
  IconAlertCircle,
  IconCheck,
  IconLoader2,
  IconRefresh,
  IconDeviceFloppy,
  IconX,
} from "@tabler/icons-react";
import type { useConfigViewModel } from "../model/useConfigViewModel";
import { FieldRenderer } from "../../../widgets/config-form/ui/FieldRenderer";
import { MarkdownHint } from "../../../shared/ui/MarkdownHint";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";

interface ConfigPageProps {
  viewModel: ReturnType<typeof useConfigViewModel>;
}

export function ConfigPage({ viewModel: vm }: ConfigPageProps) {
  const [confirmReload, setConfirmReload] = useState(false);
  const visibleCategories = vm.categories.filter(
    (category) => category.matchCount === undefined || category.matchCount > 0,
  );
  return (
    <div className="min-w-0 space-y-5">
      <div className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-secondary px-4 py-3">
        <p
          role="status"
          className={`m-0 flex items-center gap-2 text-sm ${vm.isDirty ? "text-warning" : "text-muted-foreground"}`}
        >
          {vm.loading ? (
            <IconLoader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : vm.isDirty ? (
            <IconAlertCircle aria-hidden="true" className="size-4" />
          ) : (
            <IconCheck aria-hidden="true" className="size-4" />
          )}
          {vm.loading
            ? "正在读取配置…"
            : !vm.configLoaded
              ? "配置尚未读取成功"
              : vm.isDirty
                ? "有未保存的修改"
                : "没有未保存的修改"}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={vm.loading || vm.saving}
            onClick={() => {
              if (vm.isDirty) setConfirmReload(true);
              else void vm.handleReload();
            }}
          >
            <IconRefresh aria-hidden="true" />
            重新读取
          </Button>
          <Button
            disabled={!vm.isDirty || vm.loading || !vm.configLoaded || vm.saving}
            onClick={() => void vm.handleSave()}
          >
            {vm.saving ? (
              <IconLoader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <IconDeviceFloppy aria-hidden="true" />
            )}
            {vm.saving ? "正在保存…" : "保存配置"}
          </Button>
        </div>
      </div>
      {vm.loadError && (
        <p role="alert" className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
          {vm.loadError} 请重新读取后再保存；已有编辑内容暂时保留。
        </p>
      )}
      {vm.saveError && (
        <p role="alert" className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
          {vm.saveError}
        </p>
      )}
      {vm.optionsError && (
        <p role="status" className="m-0 rounded-xl bg-warning/10 p-3 text-sm text-warning">
          {vm.optionsError}
        </p>
      )}
      <div className="grid min-w-0 gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4 self-start md:sticky md:top-20 md:max-h-[calc(100dvh-6rem)] md:overflow-y-auto">
          <div className="flex gap-1">
            <Input
              type="search"
              aria-label="搜索配置名称或说明"
              placeholder="搜索配置名称或说明"
              value={vm.searchQuery}
              onChange={(event) => vm.setSearchQuery(event.target.value)}
            />
            {vm.searchQuery && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="清除配置搜索"
                onClick={() => vm.setSearchQuery("")}
              >
                <IconX aria-hidden="true" />
              </Button>
            )}
          </div>
          <div className="md:hidden">
            <label className="mb-2 block text-sm" htmlFor="config-category">
              配置分组
            </label>
            <NativeSelect
              id="config-category"
              value={vm.activeCategory}
              disabled={visibleCategories.length === 0}
              onChange={(event) => vm.setActiveCategory(event.target.value)}
            >
              {visibleCategories.length === 0 && (
                <option value={vm.activeCategory}>没有匹配的分组</option>
              )}
              {visibleCategories.map((category) => (
                <option key={category.key} value={category.key}>
                  {category.label}
                  {vm.groupErrorCounts[category.key]
                    ? `（${vm.groupErrorCounts[category.key]} 项有误）`
                    : ""}
                </option>
              ))}
            </NativeSelect>
          </div>
          <nav
            aria-label="配置分组"
            className="hidden space-y-1 rounded-xl bg-secondary-soft p-2 md:block"
          >
            {visibleCategories.map((category) => (
              <Button
                key={category.key}
                variant={category.key === vm.activeCategory ? "default" : "ghost"}
                aria-current={category.key === vm.activeCategory ? "page" : undefined}
                className="h-auto min-h-10 w-full justify-between gap-2 whitespace-normal px-3 py-2 text-left"
                onClick={() => vm.setActiveCategory(category.key)}
              >
                <span>{category.label}</span>
                <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                  {vm.groupErrorCounts[category.key] > 0 ? (
                    <span className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-destructive">
                      {vm.groupErrorCounts[category.key]} 项有误
                    </span>
                  ) : (
                    `${category.matchCount ?? category.totalFields} 项`
                  )}
                </span>
              </Button>
            ))}
            {visibleCategories.length === 0 && !vm.loading && (
              <p className="text-sm text-muted-foreground">没有匹配的分组</p>
            )}
          </nav>
        </aside>
        <section aria-label="配置字段" aria-busy={vm.loading} className="min-w-0 space-y-5">
          {vm.activeGroupMeta && (
            <div className="space-y-2 rounded-xl border-0 border-l-2 border-solid border-primary-line bg-primary-soft px-4 py-3">
              <h2 className="m-0 text-lg font-medium">
                {vm.activeGroupMeta.description || vm.activeCategory}
              </h2>
              {vm.activeGroupMeta.hint && (
                <MarkdownHint
                  content={vm.activeGroupMeta.hint}
                  className="block text-sm leading-relaxed text-muted-foreground"
                />
              )}
            </div>
          )}
          {vm.groupErrorCounts[vm.activeCategory] > 0 && (
            <p
              role="alert"
              className="m-0 rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
            >
              当前分组内有 {vm.groupErrorCounts[vm.activeCategory]}{" "}
              项配置填写有误，请核对并修改标红字段。
            </p>
          )}
          {vm.currentGroupFields.length === 0 ? (
            <p className="py-12 text-center text-muted-foreground">
              {vm.loading
                ? "正在读取配置…"
                : vm.searchQuery
                  ? "未找到匹配该关键词的配置项"
                  : "该分组下暂无可配置字段"}
            </p>
          ) : (
            <fieldset
              disabled={vm.loading || !vm.configLoaded}
              className="m-0 grid min-w-0 grid-cols-1 gap-3 border-0 p-0 lg:grid-cols-2 disabled:opacity-60"
            >
              <legend className="sr-only">{vm.activeGroupMeta?.description || "配置字段"}</legend>
              {vm.currentGroupFields.map((field) => {
                const isLongField =
                  ["template_list", "object", "list", "text", "file"].includes(field.schema.type) ||
                  field.key.includes("prompt") ||
                  field.key.includes("template") ||
                  field.key.toLowerCase().includes("provider") ||
                  field.key.toLowerCase().includes("persona") ||
                  field.schema._special === "select_persona" ||
                  field.schema._special === "select_provider" ||
                  (field.schema.description?.length ?? 0) > 25 ||
                  (field.schema.hint?.length ?? 0) > 38;
                return (
                  <div
                    key={`${vm.activeCategory}.${field.key}`}
                    className={`min-w-0 rounded-xl border border-solid border-transparent p-4 transition-colors odd:bg-secondary-soft even:bg-card hover:border-secondary-line focus-within:border-primary-line focus-within:bg-primary-soft [&>section]:border-b-0 [&>section]:pb-0 ${isLongField ? "lg:col-span-2" : ""}`}
                  >
                    <FieldRenderer
                      fieldKey={field.key}
                      fieldSchema={field.schema}
                      value={field.value}
                      templateCdnBaseUrl={vm.templateCdnBaseUrl}
                      templateRequirements={vm.templateRequirements}
                      providers={vm.providers}
                      personas={vm.personas}
                      fullKeyPath={`${vm.activeCategory}.${field.key}`}
                      error={vm.errors[vm.activeCategory]?.[field.key]}
                      subErrors={vm.errors[vm.activeCategory]}
                      onChange={(value) =>
                        vm.handleFieldChange(vm.activeCategory, field.key, value)
                      }
                    />
                  </div>
                );
              })}
            </fieldset>
          )}
        </section>
      </div>
      <Dialog open={confirmReload} onOpenChange={setConfirmReload}>
        <DialogContent>
          <DialogTitle>放弃未保存的修改？</DialogTitle>
          <DialogDescription>
            重新读取会用已保存的配置替换当前编辑内容。读取失败时保留当前内容。
          </DialogDescription>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmReload(false)}>
              继续编辑
            </Button>
            <Button
              onClick={() => {
                setConfirmReload(false);
                void vm.handleReload();
              }}
            >
              放弃修改并重新读取
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
