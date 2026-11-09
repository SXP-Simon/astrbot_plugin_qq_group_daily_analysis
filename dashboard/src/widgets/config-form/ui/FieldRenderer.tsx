import { useId, useState } from "react";
import { IconEye, IconEyeOff, IconPlus, IconRestore, IconX } from "@tabler/icons-react";
import { resolveOptionLabel } from "../../../entities/config/model/optionLabel";
import {
  CUSTOM_RESOURCE_OPTION,
  TEMPLATE_CDN_PRESETS,
} from "../../../entities/config/model/renderingConfig";
import type { SchemaFieldItem } from "../../../entities/config/model/types";
import type { AvailableProvider, AvailablePersona } from "../../../entities/config/api/configApi";
import type { TemplateRequirements } from "../../../entities/report/model/templates";
import { MarkdownHint } from "../../../shared/ui/MarkdownHint";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";
import { Switch } from "../../../shared/ui/switch";
import { SearchSelect } from "../../../shared/ui/search-select";
import { cn } from "../../../shared/lib/cn";
import { TemplateCdnProbe } from "../../../features/test-template-cdn/ui/TemplateCdnProbe";
import { TemplateListRenderer } from "./TemplateListRenderer";
import { TemplateSelectorRenderer } from "./TemplateSelectorRenderer";
import { ConfigFileField } from "./ConfigFileField";

const TEXTAREA_CLASS =
  "min-h-28 max-h-96 w-full resize-y rounded-xl border border-solid border-input bg-background p-3 font-mono text-sm leading-relaxed text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring";

interface FieldRendererProps {
  templateRequirements?: TemplateRequirements;
  templateCdnBaseUrl?: string | null;
  fieldKey: string;
  fieldSchema: SchemaFieldItem;
  value: unknown;
  originalValue?: unknown;
  modified?: boolean;
  providers?: AvailableProvider[];
  personas?: AvailablePersona[];
  isSubField?: boolean;
  fullKeyPath?: string;
  error?: string;
  subErrors?: Record<string, string>;
  scope?: Readonly<Record<string, unknown>>;
  onChange: (value: unknown) => void;
}

export function FieldRenderer({
  templateCdnBaseUrl,
  templateRequirements,
  fieldKey,
  fieldSchema,
  value,
  originalValue,
  modified,
  providers = [],
  personas = [],
  isSubField = false,
  fullKeyPath,
  error,
  subErrors,
  scope,
  onChange,
}: FieldRendererProps) {
  const id = useId();
  const [showToken, setShowToken] = useState(false);
  const [newTag, setNewTag] = useState("");
  const title = fieldSchema.description || fieldKey;
  const hint = fieldSchema.hint || "";
  const type = fieldSchema.type;
  const options = fieldSchema.options;
  const defaultValue = fieldSchema.default;
  const current = value === undefined ? defaultValue : value;
  const stringValue = current === undefined || current === null ? "" : String(current);
  const common = {
    id,
    "aria-label": title,
    "aria-invalid": Boolean(error),
    "aria-describedby": error ? `${id}-error` : hint ? `${id}-hint` : undefined,
  };
  const resource = ["cdn_base_url", "google_fonts", "gstatic"].includes(fieldKey);
  const provider =
    type === "string" &&
    (fieldKey.toLowerCase().includes("provider") || fieldSchema._special === "select_provider");
  const persona =
    type === "string" &&
    (fieldKey.toLowerCase().includes("persona") || fieldSchema._special === "select_persona");

  const renderControl = () => {
    if (fieldKey === "service_token")
      return (
        <div className="flex items-center gap-2">
          <Input
            {...common}
            type={showToken ? "text" : "password"}
            autoComplete="new-password"
            value={stringValue}
            onChange={(event) => onChange(event.target.value)}
          />
          <Button
            variant="outline"
            size="icon"
            aria-label={showToken ? "隐藏 Token" : "显示 Token"}
            aria-pressed={showToken}
            onClick={() => setShowToken((visible) => !visible)}
          >
            {showToken ? <IconEyeOff aria-hidden="true" /> : <IconEye aria-hidden="true" />}
          </Button>
        </div>
      );
    if (resource || provider || persona) {
      const presets = resource
        ? (options
            ?.map((option, index) => ({
              value: String(option),
              label: fieldSchema.labels?.[index] || String(option),
            }))
            .filter((option) => option.value !== CUSTOM_RESOURCE_OPTION) ??
          (fieldKey === "cdn_base_url" ? TEMPLATE_CDN_PRESETS : []))
        : provider
          ? [
              { value: "", label: "使用默认模型" },
              ...providers.map((item) => ({
                value: item.id,
                label: `${item.name || item.id} [${item.id}]${item.type ? ` (${item.type})` : ""}`,
              })),
            ]
          : [
              { value: "", label: "使用默认人格" },
              ...personas.map((item) => ({
                value: item.id,
                label: `${item.name || item.id} [${item.id}]`,
              })),
            ];
      if (!resource)
        return (
          <div className="flex min-w-0 items-center gap-2">
            <div className="min-w-0 grow">
              <SearchSelect
                {...common}
                label={title}
                value={stringValue}
                options={presets}
                onChange={onChange}
                virtual
              />
            </div>
            {stringValue && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`清空 ${title}`}
                onClick={() => onChange("")}
              >
                <IconX aria-hidden="true" />
              </Button>
            )}
          </div>
        );
      return (
        <div className="grid min-w-0 gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Input
              {...common}
              className="min-w-40 basis-64 grow font-mono"
              value={stringValue}
              placeholder="选择预设，也可直接填写地址"
              onChange={(event) => onChange(event.target.value)}
            />
            {stringValue && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`清空 ${title}`}
                onClick={() => onChange("")}
              >
                <IconX aria-hidden="true" />
              </Button>
            )}
            <div className="w-32 shrink-0">
              <SearchSelect
                label={`${title}预设`}
                triggerText="选择预设"
                value={stringValue}
                options={presets}
                onChange={onChange}
                virtual
              />
            </div>
          </div>
          {fieldKey === "cdn_base_url" &&
            (stringValue.trim() ? (
              <TemplateCdnProbe baseUrl={stringValue} />
            ) : (
              <p className="m-0 text-sm text-muted-foreground">
                先选择或填写地址，即可检测 CDN；留空使用当前资源环境的预设。
              </p>
            ))}
        </div>
      );
    }
    if (type === "template_list")
      return (
        <TemplateListRenderer
          templateCdnBaseUrl={templateCdnBaseUrl}
          fieldKey={fieldKey}
          fieldSchema={fieldSchema}
          value={value}
          originalValue={originalValue}
          modified={modified}
          providers={providers}
          personas={personas}
          fullKeyPath={fullKeyPath || fieldKey}
          onChange={onChange}
        />
      );
    if (
      type === "object" &&
      fieldSchema.items &&
      typeof fieldSchema.items === "object" &&
      !Array.isArray(fieldSchema.items) &&
      typeof fieldSchema.items.type !== "string"
    ) {
      const items = fieldSchema.items as Record<string, SchemaFieldItem>;
      const object =
        current !== null && typeof current === "object" && !Array.isArray(current)
          ? (current as Record<string, unknown>)
          : {};
      const original =
        originalValue !== null && typeof originalValue === "object" && !Array.isArray(originalValue)
          ? (originalValue as Record<string, unknown>)
          : {};
      return (
        <div className="grid min-w-0 gap-4 border-0 border-l border-solid border-border pl-4">
          {Object.entries(items).map(([key, definition]) => {
            if (definition.invisible || definition.hidden) return null;
            const path = `${fullKeyPath || fieldKey}.${key}`;
            return (
              <FieldRenderer
                key={key}
                fieldKey={key}
                fieldSchema={definition}
                value={object[key] === undefined ? definition.default : object[key]}
                originalValue={original[key] === undefined ? definition.default : original[key]}
                modified={
                  modified === undefined
                    ? undefined
                    : JSON.stringify(object[key] ?? definition.default) !==
                      JSON.stringify(original[key] ?? definition.default)
                }
                providers={providers}
                personas={personas}
                isSubField
                fullKeyPath={path}
                templateCdnBaseUrl={templateCdnBaseUrl}
                templateRequirements={templateRequirements}
                scope={scope}
                error={subErrors?.[key] || subErrors?.[path]}
                subErrors={subErrors}
                onChange={(next) => onChange({ ...object, [key]: next })}
              />
            );
          })}
        </div>
      );
    }
    if (type === "bool") {
      const checked = typeof current === "boolean" ? current : Boolean(defaultValue);
      return (
        <div className="flex items-center gap-3">
          <Switch {...common} checked={checked} onCheckedChange={onChange} />
          <span className="text-sm text-muted-foreground">{checked ? "已启用" : "已关闭"}</span>
        </div>
      );
    }
    if (fieldKey.includes("report_template"))
      return (
        <TemplateSelectorRenderer
          cdnBaseUrl={templateCdnBaseUrl}
          requirements={templateRequirements}
          value={value}
          options={options}
          defaultValue={defaultValue}
          onChange={onChange}
        />
      );
    if (["string", "int", "float"].includes(type) && options?.length) {
      const selected = String(current ?? options[0]);
      return (
        <NativeSelect
          {...common}
          value={selected}
          onChange={(event) =>
            onChange(type === "string" ? event.target.value : Number(event.target.value))
          }
        >
          {!options.some((option) => String(option) === selected) && (
            <option value={selected}>{selected}（已有值）</option>
          )}
          {options.map((option) => (
            <option key={String(option)} value={String(option)}>
              {resolveOptionLabel(String(option), options, fieldSchema.labels)}
            </option>
          ))}
        </NativeSelect>
      );
    }
    if (
      type === "text" ||
      (type === "string" && (fieldKey.includes("template") || fieldKey.includes("prompt")))
    )
      return (
        <textarea
          {...common}
          className={TEXTAREA_CLASS}
          rows={6}
          value={typeof current === "string" ? current : ""}
          onChange={(event) => onChange(event.target.value)}
        />
      );
    if (type === "int" || type === "float")
      return (
        <Input
          {...common}
          type="number"
          className="max-w-60 tabular-nums"
          step={type === "float" ? 0.1 : 1}
          min={typeof fieldSchema.min === "number" ? fieldSchema.min : undefined}
          max={typeof fieldSchema.max === "number" ? fieldSchema.max : undefined}
          value={typeof current === "number" ? current : 0}
          onChange={(event) => onChange(event.target.value === "" ? 0 : Number(event.target.value))}
        />
      );
    if (
      type === "file" ||
      fieldSchema._special === "image_list" ||
      fieldKey === "reference_images" ||
      fieldKey === "drawing_reference_image"
    )
      return (
        <ConfigFileField
          value={value}
          multiple={Array.isArray(defaultValue) || Array.isArray(value)}
          path={
            fullKeyPath ||
            (fieldKey === "reference_images"
              ? "daily_comic.comic_characters.templates.character.reference_images"
              : fieldKey)
          }
          fileTypes={
            Array.isArray(fieldSchema.file_types)
              ? fieldSchema.file_types.filter((item): item is string => typeof item === "string")
              : undefined
          }
          scope={scope}
          onChange={onChange}
        />
      );
    if (type === "list") {
      const items = fieldSchema.items as SchemaFieldItem | undefined;
      const choices = options?.length
        ? options.map(String)
        : Array.isArray(items?.options)
          ? items.options.map(String)
          : Array.isArray(items?.enum)
            ? items.enum.map(String)
            : null;
      const values = Array.isArray(current)
        ? current.map(String)
        : typeof current === "string" && current
          ? [current]
          : [];
      const labels: Record<string, string> =
        fieldKey === "output_format"
          ? { image: "图片报告 (image)", text: "纯文本摘要 (text)", html: "HTML 网页报告 (html)" }
          : {};
      if (choices?.length)
        return (
          <div className="grid gap-2">
            <div role="group" aria-label={title} className="flex flex-wrap gap-2">
              {[...new Set([...choices, ...values])].map((choice) => (
                <label
                  key={choice}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg border border-solid px-3 py-2 text-sm",
                    values.includes(choice) ? "border-primary/50 bg-primary/10" : "border-border",
                  )}
                >
                  <input
                    type="checkbox"
                    className="size-4 accent-primary focus-visible:outline-2 focus-visible:outline-ring"
                    checked={values.includes(choice)}
                    onChange={(event) =>
                      onChange(
                        event.target.checked
                          ? [...values, choice]
                          : values.filter((entry) => entry !== choice),
                      )
                    }
                  />
                  {labels[choice] || resolveOptionLabel(choice, choices, fieldSchema.labels)}
                </label>
              ))}
            </div>
            {fieldKey === "output_format" && values.length > 0 && (
              <p className="m-0 text-xs text-muted-foreground">
                发送顺序：{values.map((entry) => labels[entry] || entry).join(" → ")}
              </p>
            )}
          </div>
        );
      const add = () => {
        const next = newTag.trim();
        if (next && !values.includes(next)) onChange([...values, next]);
        setNewTag("");
      };
      return (
        <div className="grid gap-2">
          <div className="flex flex-wrap gap-2">
            {values.map((entry, index) => (
              <span
                key={`${entry}:${index}`}
                className="inline-flex max-w-full items-center gap-1 rounded-lg bg-secondary px-2 py-1 text-sm"
              >
                <code className="break-all text-xs">{entry}</code>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-1"
                  aria-label={`移除 ${entry}`}
                  onClick={() => onChange(values.filter((_, i) => i !== index))}
                >
                  <IconX aria-hidden="true" />
                </Button>
              </span>
            ))}
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <Input
              className="max-w-sm font-mono"
              aria-label={`添加${title}`}
              value={newTag}
              onChange={(event) => setNewTag(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  add();
                }
              }}
            />
            <Button variant="outline" disabled={!newTag.trim()} onClick={add}>
              <IconPlus aria-hidden="true" />
              添加条目
            </Button>
          </div>
        </div>
      );
    }
    if (type === "string")
      return (
        <div className="flex min-w-0 items-center gap-2">
          <Input
            {...common}
            value={stringValue}
            className={/id|key|url|path/i.test(fieldKey) ? "font-mono" : undefined}
            onChange={(event) => onChange(event.target.value)}
          />
          {stringValue && (
            <Button
              variant="ghost"
              size="icon"
              aria-label={`清空 ${title}`}
              onClick={() => onChange("")}
            >
              <IconX aria-hidden="true" />
            </Button>
          )}
        </div>
      );
    return (
      <textarea
        {...common}
        className={TEXTAREA_CLASS}
        rows={6}
        value={
          typeof current === "object" ? JSON.stringify(current, null, 2) : String(current ?? "")
        }
        onChange={(event) => {
          try {
            const parsed: unknown = JSON.parse(event.target.value);
            onChange(parsed);
          } catch {
            onChange(event.target.value);
          }
        }}
      />
    );
  };

  return (
    <section
      id={`cfg-field-${fullKeyPath ? fullKeyPath.replace(/\./g, "-") : fieldKey}`}
      data-field-key={fieldKey}
      data-modified={modified || undefined}
      className={cn(
        "grid min-w-0 gap-3 border-0 border-b border-solid border-border",
        isSubField ? "pb-3" : "pb-5",
        modified && isSubField && !error && "rounded-xl border-primary-line p-3",
        modified &&
          isSubField &&
          !error &&
          !["object", "template_list"].includes(type) &&
          "bg-primary-soft",
        error && "rounded-xl border border-destructive/40 bg-destructive/5 p-3",
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <label
            htmlFor={id}
            title={fullKeyPath || fieldKey}
            className={cn("text-sm font-medium", error && "text-destructive")}
          >
            {title}
          </label>
          {modified && (
            <span className="rounded-md bg-primary-soft px-2 py-0.5 text-xs text-primary-ink">
              已修改
            </span>
          )}
        </div>
        {defaultValue !== undefined && JSON.stringify(value) !== JSON.stringify(defaultValue) && (
          <Button
            variant="ghost"
            size="sm"
            title="重置为此项默认值"
            onClick={() => onChange(structuredClone(defaultValue))}
          >
            <IconRestore aria-hidden="true" />
            恢复默认
          </Button>
        )}
      </div>
      {renderControl()}
      {error && (
        <p id={`${id}-error`} role="alert" className="m-0 text-sm text-destructive">
          {error}
        </p>
      )}
      {hint && (
        <div id={`${id}-hint`} className="text-sm leading-relaxed text-muted-foreground">
          <MarkdownHint content={hint} />
        </div>
      )}
    </section>
  );
}
