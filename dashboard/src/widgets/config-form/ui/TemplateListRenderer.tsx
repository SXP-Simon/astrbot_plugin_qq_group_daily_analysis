import { useRef, useState } from "react";
import { IconArrowDown, IconArrowUp, IconPlus, IconTrash } from "@tabler/icons-react";
import { isFieldVisible } from "../../../entities/config/model/visibility";
import type { SchemaFieldItem } from "../../../entities/config/model/types";
import type { AvailableProvider, AvailablePersona } from "../../../entities/config/api/configApi";
import { FieldRenderer } from "./FieldRenderer";
import { T2iProbe } from "../../../features/test-t2i/ui/T2iProbe";
import { TemplateResources } from "../../../features/manage-template-resources/ui/TemplateResources";
import { TypstFonts } from "../../../features/manage-typst-fonts/ui/TypstFonts";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../entities/config/model/renderingConfig";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import { useTemplateListModel } from "../model/useTemplateListModel";

interface TemplateListRendererProps {
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  providers?: AvailableProvider[];
  personas?: AvailablePersona[];
  fullKeyPath?: string;
  onChange: (val: unknown) => void;
}

export function TemplateListRenderer({
  fieldKey,
  fieldSchema,
  value,
  providers = [],
  personas = [],
  fullKeyPath,
  onChange,
}: TemplateListRendererProps) {
  const vm = useTemplateListModel(fieldSchema, value, onChange);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<{
    index: number;
    item: Record<string, unknown>;
    name: string;
  } | null>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const deleted = useRef(false);
  const nativePlan = vm.items.find((item) => vm.templateKey(item) === "typst");
  const nativeCdn = String(
    (nativePlan?.cdn_base_url === "__custom__"
      ? nativePlan?.custom_cdn_base_url
      : nativePlan?.cdn_base_url) || DEFAULT_TEMPLATE_CDN_BASE_URL,
  );
  const deleteCurrent = deleting !== null && vm.items[deleting.index] === deleting.item;
  const addLabel = fieldKey === "t2i_rendering_strategies" ? "添加渲染方案" : "添加配置项";

  return (
    <div className="min-w-0 space-y-4">
      {!vm.valid && (
        <p role="alert" className="text-sm text-destructive">
          配置条目格式不正确，请检查原始配置。当前内容未被改写。
        </p>
      )}
      {vm.valid && !vm.items.length && (
        <p className="py-3 text-sm text-muted-foreground">暂无配置条目，可在下方添加。</p>
      )}
      <div className="space-y-6">
        {vm.items.map((item, index) => {
          const itemTemplateKey = vm.templateKey(item) ?? "character";
          const template = vm.templates[itemTemplateKey];
          const subItems = template?.items ?? {};
          const itemContext = {
            ...Object.fromEntries(
              Object.entries(subItems).map(([key, field]) => [key, field.default]),
            ),
            ...item,
          };
          const name = String(item.name || template?.name || `条目 ${index + 1}`);
          return (
            <section
              key={`${fieldKey}_${index}`}
              aria-label={`${index + 1}. ${name}`}
              className="min-w-0 space-y-4 border-0 border-b border-solid border-border pb-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-secondary/60 px-3 py-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <h3 className="m-0 break-words text-base font-medium">
                    {index + 1}. {name}
                  </h3>
                  {item.priority !== undefined && (
                    <span className="rounded-md bg-info/10 px-2 py-1 text-xs text-info">
                      优先级 {String(item.priority)}
                    </span>
                  )}
                  {item.enable !== undefined && (
                    <span
                      className={`rounded-md px-2 py-1 text-xs ${item.enable ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}
                    >
                      {item.enable ? "已启用" : "已禁用"}
                    </span>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`上移 ${name}`}
                    disabled={index === 0}
                    onClick={() => vm.move(index, -1)}
                  >
                    <IconArrowUp aria-hidden="true" />
                    上移
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`下移 ${name}`}
                    disabled={index === vm.items.length - 1}
                    onClick={() => vm.move(index, 1)}
                  >
                    <IconArrowDown aria-hidden="true" />
                    下移
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:bg-destructive/10"
                    aria-label={`删除 ${name}`}
                    onClick={() => {
                      deleted.current = false;
                      setDeleting({ index, item, name });
                    }}
                  >
                    <IconTrash aria-hidden="true" />
                    删除
                  </Button>
                </div>
              </div>
              <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
                {Object.entries(subItems)
                  .filter(([, field]) => isFieldVisible(field, { item: itemContext }))
                  .map(([key, field]) => {
                    const fullWidth =
                      ["template_list", "text", "file", "object"].includes(field.type) ||
                      ["prompt", "image", "url", "key"].some((part) => key.includes(part));
                    return (
                      <div key={key} className={fullWidth ? "min-w-0 xl:col-span-2" : "min-w-0"}>
                        <FieldRenderer
                          fieldKey={key}
                          fieldSchema={field}
                          value={item[key] !== undefined ? item[key] : field.default}
                          providers={providers}
                          personas={personas}
                          isSubField
                          scope={item}
                          fullKeyPath={`${fullKeyPath || fieldKey}.templates.${itemTemplateKey}.${key}`}
                          onChange={(next) => vm.change(index, key, next)}
                        />
                      </div>
                    );
                  })}
              </div>
              {fieldKey === "t2i_rendering_strategies" && (
                <>
                  {itemTemplateKey === "typst" && (
                    <TypstFonts
                      cdnBaseUrl={String(
                        (item.cdn_base_url === "__custom__"
                          ? item.custom_cdn_base_url
                          : item.cdn_base_url) || DEFAULT_TEMPLATE_CDN_BASE_URL,
                      )}
                    />
                  )}
                  <T2iProbe
                    input={{
                      render_service:
                        itemTemplateKey === "typst"
                          ? "typst"
                          : itemTemplateKey === "custom"
                            ? "custom"
                            : "astrbot",
                      service_endpoint: item.service_endpoint,
                      service_token: item.service_token,
                      timeout: item.timeout,
                      request_timeout: item.request_timeout,
                      raster_ppi: item.raster_ppi,
                    }}
                  />
                </>
              )}
            </section>
          );
        })}
      </div>
      {vm.templateKeys.length > 0 && (
        <Button
          ref={addButton}
          variant="outline"
          disabled={!vm.valid}
          className="text-info"
          onClick={() =>
            vm.templateKeys.length === 1 ? vm.add(vm.templateKeys[0]) : setAdding(true)
          }
        >
          <IconPlus aria-hidden="true" />
          {addLabel}
        </Button>
      )}
      {fieldKey === "t2i_rendering_strategies" && nativePlan && (
        <TemplateResources cdnBaseUrl={nativeCdn} />
      )}
      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent>
          <DialogTitle>{addLabel}</DialogTitle>
          <DialogDescription>选择要添加的类型，添加后可继续调整各项设置。</DialogDescription>
          <div className="grid gap-2">
            {vm.templateKeys.map((key) => (
              <Button
                key={key}
                variant="outline"
                className="h-auto flex-col items-start gap-1 whitespace-normal py-3 text-left"
                onClick={() => {
                  vm.add(key);
                  setAdding(false);
                }}
              >
                <span>{vm.templates[key].name || key}</span>
                {vm.templates[key].description && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {vm.templates[key].description}
                  </span>
                )}
              </Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
      >
        <DialogContent
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelButton.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            if (deleted.current) {
              event.preventDefault();
              addButton.current?.focus();
            }
          }}
        >
          <DialogTitle>删除配置条目？</DialogTitle>
          <DialogDescription>将移除“{deleting?.name}”。保存配置后生效。</DialogDescription>
          {deleting && !deleteCurrent && (
            <p role="alert" className="text-sm text-warning">
              条目已变更，请关闭后重新选择。
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button ref={cancelButton} variant="outline" onClick={() => setDeleting(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={!deleteCurrent}
              onClick={() => {
                if (deleting && deleteCurrent) {
                  vm.remove(deleting.index);
                  deleted.current = true;
                  setDeleting(null);
                }
              }}
            >
              确认删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
