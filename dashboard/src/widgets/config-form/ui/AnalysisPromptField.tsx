import { useCallback, useId, useRef, useState } from "react";
import { IconAlertCircle, IconEye, IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import {
  expandAnalysisPrompt,
  readPromptSchemes,
  type PromptScheme,
} from "../../../entities/config/model/promptSchemes";
import type { PromptVariable } from "../../../entities/config/model/types";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import { Input } from "../../../shared/ui/input";
import { usePromptTextHistory } from "../model/usePromptTextHistory";
import { PromptVariablePanel } from "./PromptVariablePanel";

const fieldErrorClass =
  "m-0 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive [overflow-wrap:anywhere]";

interface AnalysisPromptFieldProps {
  title: string;
  activeText: string;
  savedText: string;
  defaultText: string;
  schemes: unknown;
  savedSchemes: unknown;
  variables: Record<string, PromptVariable>;
  exampleConfig?: Readonly<Record<string, unknown>>;
  validationPath?: string;
  error?: string;
  onChange: (schemes: PromptScheme[]) => void;
}

export function AnalysisPromptField({
  title,
  activeText,
  savedText,
  defaultText,
  schemes,
  savedSchemes,
  variables,
  exampleConfig,
  validationPath,
  error,
  onChange,
}: AnalysisPromptFieldProps) {
  const id = useId();
  const nameInput = useRef<HTMLInputElement>(null);
  const [edit, setEdit] = useState<{ index: number; name: string; text: string }>();
  const [deleting, setDeleting] = useState<number>();
  const [showPreview, setShowPreview] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const rows = readPromptSchemes(schemes, activeText);
  const saved = readPromptSchemes(savedSchemes, savedText);
  const expanded = edit ? expandAnalysisPrompt(edit.text, variables, exampleConfig) : undefined;
  const readOnly = edit?.index === 0;
  const updateText = useCallback((text: string) => {
    setEdit((current) => (current ? { ...current, text } : current));
  }, []);
  const textHistory = usePromptTextHistory(
    Boolean(edit) && !readOnly,
    edit?.text ?? "",
    updateText,
  );
  const name = edit?.name.trim() ?? "";
  const formatToken = (key: string) => "${" + key + "}";
  const nameProblem = !name
    ? "请填写方案名称"
    : rows.some((row, index) => row.name === name && index !== edit?.index)
      ? "已有同名方案，请换一个名称"
      : "";
  const bodyProblem = !edit?.text.trim()
    ? "请填写提示词正文"
    : expanded?.missing.length
      ? `请插入必填变量 ${expanded.missing.map(formatToken).join("、")}`
      : expanded?.unknown.length
        ? `不支持变量 ${expanded.unknown.map(formatToken).join("、")}`
        : "";
  const nameError = attempted && !readOnly ? nameProblem : "";
  const bodyError = attempted && !readOnly ? bodyProblem : "";

  const open = (index: number) => {
    const row = rows[index];
    setShowPreview(false);
    setAttempted(false);
    textHistory.reset();
    setEdit({
      index,
      name: row?.name ?? "",
      text: row?.text ?? defaultText,
    });
  };

  return (
    <div data-config-path={validationPath} className="grid min-w-0 gap-3">
      <fieldset className="m-0 grid min-w-0 gap-2 border-0 p-0">
        <legend className="mb-2 text-sm font-medium">{title}</legend>
        {error && (
          <p role="alert" className={fieldErrorClass}>
            <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        )}
        {rows.map((row, index) => {
          const label = row.name ?? "原有配置";
          const persisted = saved.some(
            (entry) => entry.name === row.name && entry.text === row.text,
          );
          return (
            <div
              key={row.name ?? 0}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-solid border-border bg-card px-3 py-2"
            >
              <label className="flex min-w-0 cursor-pointer flex-wrap items-center gap-2 text-sm">
                <input
                  type="radio"
                  className="size-4 accent-primary"
                  name={id}
                  checked={row.selected}
                  onChange={() =>
                    onChange(rows.map((entry, i) => ({ ...entry, selected: i === index })))
                  }
                />
                <span className="break-all">{label}</span>
                {row.name !== null && (
                  <span className="rounded-md bg-primary-soft px-2 py-0.5 text-xs text-primary-ink">
                    自定义 · {persisted ? "已保存" : "待保存"}
                  </span>
                )}
              </label>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={index === 0 ? `查看${title}原有配置` : `编辑 ${label}`}
                  onClick={() => open(index)}
                >
                  {index === 0 ? <IconEye aria-hidden="true" /> : <IconPencil aria-hidden="true" />}
                  {index === 0 ? "查看" : "编辑"}
                </Button>
                {index > 0 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    aria-label={`删除 ${label}`}
                    onClick={() => setDeleting(index)}
                  >
                    <IconTrash aria-hidden="true" />
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </fieldset>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Button size="sm" variant="outline" onClick={() => open(-1)}>
          <IconPlus aria-hidden="true" />
          新建自定义方案
        </Button>
        <span className="text-xs text-muted-foreground">
          新方案以插件内置提示词为起点，选中并保存配置后生效。
        </span>
      </div>

      <Dialog open={edit !== undefined} onOpenChange={(open) => !open && setEdit(undefined)}>
        <DialogContent className="max-w-5xl">
          <DialogTitle>
            {title} · {readOnly ? "原有配置" : "自定义方案"}
          </DialogTitle>
          <DialogDescription>
            预览时，变量会换成示例内容，数量上限沿用当前配置。运行分析时会填入当次数据。
          </DialogDescription>
          {edit && (
            <form
              className="grid min-w-0 gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (readOnly) return;
                if (nameProblem || bodyProblem) {
                  setAttempted(true);
                  (nameProblem ? nameInput.current : textHistory.fieldRef.current)?.focus();
                  return;
                }
                const next = rows.slice();
                if (edit.index === -1) {
                  next.push({ name, text: edit.text, selected: false });
                } else {
                  next[edit.index] = { ...next[edit.index], name, text: edit.text };
                }
                onChange(next);
                setEdit(undefined);
              }}
            >
              {!readOnly && (
                <div className="grid gap-1 text-sm">
                  <label htmlFor={`${id}-name`}>方案名称</label>
                  <Input
                    id={`${id}-name`}
                    ref={nameInput}
                    value={edit.name}
                    onChange={(event) => setEdit({ ...edit, name: event.target.value })}
                    placeholder="例如：偏技术讨论"
                    aria-invalid={Boolean(nameError)}
                    aria-describedby={nameError ? `${id}-name-error` : undefined}
                    className="aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive"
                  />
                  {nameError && (
                    <p id={`${id}-name-error`} role="alert" className={fieldErrorClass}>
                      <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                      {nameError}
                    </p>
                  )}
                </div>
              )}
              <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(13rem,0.48fr)]">
                <div className="grid min-w-0 content-start gap-2 text-sm">
                  <label htmlFor={`${id}-body`}>提示词正文</label>
                  {bodyError && (
                    <p id={`${id}-body-error`} role="alert" className={fieldErrorClass}>
                      <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                      {bodyError}
                    </p>
                  )}
                  <textarea
                    id={`${id}-body`}
                    ref={textHistory.fieldRef}
                    value={edit.text}
                    readOnly={readOnly}
                    placeholder={readOnly ? "原有提示词正文为空。" : undefined}
                    onChange={textHistory.onChange}
                    onCompositionStart={textHistory.onCompositionStart}
                    onKeyDown={readOnly ? undefined : textHistory.onKeyDown}
                    aria-invalid={Boolean(bodyError)}
                    aria-describedby={bodyError ? `${id}-body-error` : undefined}
                    className="min-h-64 max-h-[55dvh] w-full resize-y rounded-xl border border-solid border-input bg-background p-3 font-mono text-sm leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive"
                  />
                </div>
                <PromptVariablePanel
                  variables={variables}
                  exampleFor={(key) =>
                    expandAnalysisPrompt(formatToken(key), variables, exampleConfig).expanded
                  }
                  onInsert={readOnly ? undefined : textHistory.insert}
                />
              </div>
              {showPreview && (
                <section
                  id={`${id}-preview`}
                  aria-labelledby={`${id}-preview-title`}
                  className="grid min-w-0 gap-2"
                >
                  <h3 id={`${id}-preview-title`} className="m-0 text-sm font-medium">
                    填入示例数据后的提示词
                  </h3>
                  <pre className="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-secondary-soft p-3 text-xs leading-relaxed">
                    {expanded?.expanded || "没有可预览的正文"}
                  </pre>
                </section>
              )}
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  aria-expanded={showPreview}
                  aria-controls={showPreview ? `${id}-preview` : undefined}
                  onClick={() => setShowPreview(!showPreview)}
                >
                  <IconEye aria-hidden="true" />
                  {showPreview ? "收起预览" : "用示例数据预览"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setEdit(undefined)}>
                  {readOnly ? "返回" : "取消"}
                </Button>
                {!readOnly && <Button type="submit">应用到草稿</Button>}
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleting !== undefined}
        onOpenChange={(open) => !open && setDeleting(undefined)}
      >
        <DialogContent>
          <DialogTitle>删除自定义方案？</DialogTitle>
          <DialogDescription>
            保存配置后「{deleting === undefined ? "" : rows[deleting]?.name}」会被删除。
            {deleting !== undefined && rows[deleting]?.selected && " 此模块将切回原有配置。"}
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleting(undefined)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleting === undefined) return;
                const next = rows.filter((_, index) => index !== deleting);
                if (rows[deleting]?.selected) next[0] = { ...next[0], selected: true };
                onChange(next);
                setDeleting(undefined);
              }}
            >
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
