import { useRef, useState } from "react";
import { IconArrowDown, IconArrowUp, IconPlus, IconTrash } from "@tabler/icons-react";
import { isFieldVisible } from "../../../entities/config/model/visibility";
import type { SchemaFieldItem } from "../../../entities/config/model/types";
import type { AvailableProvider, AvailablePersona } from "../../../entities/config/api/configApi";
import { FieldRenderer } from "./FieldRenderer";
import { ComicStyleGallery } from "./ComicStyleGallery";
import { comicPresets } from "../../../entities/comic/model/comicPresets";
import { T2iProbe } from "../../../features/test-t2i/ui/T2iProbe";
import { TemplateResources } from "../../../features/manage-template-resources/ui/TemplateResources";
import { TypstFonts } from "../../../features/manage-typst-fonts/ui/TypstFonts";
import { DEFAULT_TEMPLATE_CDN_BASE_URL } from "../../../entities/config/model/renderingConfig";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import { useTemplateListModel } from "../model/useTemplateListModel";

interface TemplateListRendererProps {
  templateCdnBaseUrl?: string | null;
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  originalValue?: unknown;
  modified?: boolean;
  providers?: AvailableProvider[];
  personas?: AvailablePersona[];
  fullKeyPath?: string;
  onChange: (val: unknown) => void;
}

export function TemplateListRenderer({
  templateCdnBaseUrl,
  fieldKey,
  fieldSchema,
  value,
  originalValue,
  modified,
  providers = [],
  personas = [],
  fullKeyPath,
  onChange,
}: TemplateListRendererProps) {
  const vm = useTemplateListModel(fieldSchema, value, onChange, originalValue);
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
  const comicStyles = fieldKey === "comic_styles";
  const savedComicStyles: { value: string; label: string; name: string; prompt: string }[] = [];
  if (comicStyles) {
    for (const [index, item] of vm.savedItems.entries()) {
      const { name, prompt_override: prompt } = item;
      if (
        item.preset_id !== "custom" ||
        typeof name !== "string" ||
        !name.trim() ||
        typeof prompt !== "string" ||
        !prompt.trim() ||
        savedComicStyles.some((style) => style.name === name && style.prompt === prompt)
      )
        continue;
      const duplicate = savedComicStyles.filter((style) => style.name === name).length;
      savedComicStyles.push({
        value: `saved:${index}`,
        label: `${name}${duplicate ? `（${duplicate + 1}）` : ""}（自定义）`,
        name,
        prompt,
      });
    }
  }
  const removesSavedComicStyle =
    deleteCurrent &&
    deleting.item.preset_id === "custom" &&
    savedComicStyles.some(
      (style) =>
        style.name === deleting.item.name && style.prompt === deleting.item.prompt_override,
    ) &&
    !vm.items.some(
      (item, index) =>
        index !== deleting.index &&
        item.preset_id === "custom" &&
        item.name === deleting.item.name &&
        item.prompt_override === deleting.item.prompt_override,
    );
  const comicCharacters = fieldKey === "comic_characters";
  const addLabel =
    {
      comic_styles: "添加风格方案",
      comic_characters: "添加角色方案",
      t2i_rendering_strategies: "添加渲染方案",
    }[fieldKey] ?? "添加配置项";

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
          const original = vm.originalItems[index] ?? {};
          const subItems = template?.items ?? {};
          const itemContext = {
            ...Object.fromEntries(
              Object.entries(subItems).map(([key, field]) => [key, field.default]),
            ),
            ...item,
          };
          const preset = comicStyles
            ? comicPresets.find(({ id }) => item.preset_id === id)
            : undefined;
          const customStyle = comicStyles && item.preset_id === "custom";
          const savedStyle = customStyle
            ? savedComicStyles.find(
                (style) => style.name === item.name && style.prompt === item.prompt_override,
              )
            : undefined;
          const name = String(
            item.name ||
              (customStyle ? "自定义风格" : preset?.name) ||
              template?.name ||
              `条目 ${index + 1}`,
          );
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
                  {customStyle && (
                    <span className="rounded-md bg-secondary-soft px-2 py-1 text-xs text-secondary-ink">
                      自定义
                    </span>
                  )}
                  {item.priority !== undefined && (
                    <span className="rounded-md bg-secondary-soft px-2 py-1 text-xs text-secondary-ink">
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
              {comicStyles && !customStyle && (
                <div className="flex flex-wrap items-center gap-2">
                  <ComicStyleGallery
                    cdnBaseUrl={templateCdnBaseUrl}
                    selected={item.preset_id}
                    onSelect={(id) => vm.change(index, { preset_id: id })}
                  />
                  {preset && !String(item.prompt_override ?? "").trim() && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => vm.change(index, { prompt_override: preset.prompt })}
                    >
                      复制内置提示词并编辑
                    </Button>
                  )}
                  {String(item.prompt_override ?? "").trim() && (
                    <span className="text-sm text-muted-foreground">
                      此方案正在使用自定义提示词
                    </span>
                  )}
                </div>
              )}
              {comicCharacters &&
                typeof item.storyboard_prompt === "string" &&
                item.storyboard_prompt.trim() && (
                  <p className="m-0 text-sm text-muted-foreground">
                    此角色仍在使用旧版专属提示词。清空下方正文后，会跟随漫画风格方案。
                  </p>
                )}
              <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
                {Object.entries(subItems)
                  .filter(
                    ([key, field]) =>
                      (!comicCharacters ||
                        key !== "storyboard_prompt" ||
                        (typeof item.storyboard_prompt === "string" &&
                          item.storyboard_prompt.trim())) &&
                      isFieldVisible(field, { item: itemContext }),
                  )
                  .map(([key, field]) => {
                    const styleSource = comicStyles && key === "preset_id";
                    let displayField = field;
                    if (styleSource && (customStyle || savedComicStyles.length)) {
                      displayField = {
                        ...field,
                        hint: customStyle
                          ? "下拉框显示上次保存的方案。删除最后一条同名且正文相同的自定义方案，或把它切换为其他风格后保存，该选项会消失。暂时不用时，可以关闭「启用此方案」再保存，保留下拉选项。"
                          : field.hint,
                        options: [
                          ...savedComicStyles.map(({ value }) => value),
                          ...(field.options ?? []),
                        ],
                        labels: [
                          ...savedComicStyles.map(({ label }) => label),
                          ...(field.labels ?? []),
                        ],
                      };
                    } else if (customStyle && key === "prompt_override") {
                      displayField = {
                        ...field,
                        default: undefined,
                        hint: "填写完整分镜提示词。可用 `${chat_content}` 指定话题位置，未写此变量时会把群聊话题附在正文末尾。",
                      };
                    } else if (customStyle && key === "name") {
                      displayField = { ...field, hint: "填写便于辨认的自定义风格名称。" };
                    }
                    const fullWidth =
                      ["template_list", "text", "file", "object"].includes(field.type) ||
                      ["prompt", "image", "url", "key"].some((part) => key.includes(part));
                    return (
                      <div key={key} className={fullWidth ? "min-w-0 xl:col-span-2" : "min-w-0"}>
                        <FieldRenderer
                          fieldKey={key}
                          fieldSchema={displayField}
                          value={
                            (styleSource ? savedStyle?.value : undefined) ??
                            (item[key] !== undefined ? item[key] : field.default)
                          }
                          originalValue={
                            original[key] !== undefined ? original[key] : field.default
                          }
                          modified={
                            modified === undefined
                              ? undefined
                              : JSON.stringify(item[key] ?? field.default) !==
                                JSON.stringify(original[key] ?? field.default)
                          }
                          providers={providers}
                          personas={personas}
                          isSubField
                          scope={item}
                          fullKeyPath={`${fullKeyPath || fieldKey}.templates.${itemTemplateKey}.${key}`}
                          onChange={(next) => {
                            const selected = styleSource
                              ? savedComicStyles.find(({ value }) => value === next)
                              : undefined;
                            vm.change(
                              index,
                              selected
                                ? {
                                    preset_id: "custom",
                                    name: selected.name,
                                    prompt_override: selected.prompt,
                                  }
                                : { [key]: next },
                            );
                          }}
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
          className="text-secondary-ink"
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
          <DialogDescription>
            将移除“{deleting?.name}”。保存配置后生效。
            {removesSavedComicStyle && (
              <span className="mt-2 block text-warning">
                保存后，此自定义风格会从下拉框消失。暂时不用时，可取消删除并关闭「启用此方案」，保留该选项。
              </span>
            )}
          </DialogDescription>
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
