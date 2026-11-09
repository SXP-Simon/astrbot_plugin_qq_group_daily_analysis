import { useId, useState, type TextareaHTMLAttributes } from "react";
import { IconAlertCircle, IconBraces, IconEye } from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import {
  readComicStoryboard,
  storyboardVariables,
} from "@/entities/comic/model/comicStoryboardPrompt";
import { usePromptTextHistory } from "@/widgets/config-form/model/usePromptTextHistory";
import { PromptVariablePanel } from "./PromptVariablePanel";

interface ComicStoryboardEditorProps {
  inputProps: TextareaHTMLAttributes<HTMLTextAreaElement>;
  text: string;
  presetPrompt?: string;
  allowEmpty: boolean;
  onChange: (text: string) => void;
}

export function ComicStoryboardEditor({
  inputProps,
  text,
  presetPrompt,
  allowEmpty,
  onChange,
}: ComicStoryboardEditorProps) {
  const id = useId();
  const [draft, setDraft] = useState<string>();
  const [showPreview, setShowPreview] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const history = usePromptTextHistory(draft !== undefined, draft ?? "", setDraft);
  const initialText = !text.trim() && presetPrompt ? presetPrompt : text;
  const legacyBraces =
    draft &&
    !draft.includes("$") &&
    /\{\{|\}\}|\{(?:chat_content|topic_count|max_count)(?:\}|!|:|\.|\[)/.test(draft);
  const storyboard = readComicStoryboard(draft ?? "");
  const problem = draft?.trim() ? storyboard.error : allowEmpty ? "" : "请填写分镜提示词";
  const error = attempted ? problem : "";

  return (
    <div className="grid min-w-0 justify-items-start gap-2">
      <textarea {...inputProps} value={text} onChange={(event) => onChange(event.target.value)} />
      <Dialog
        open={draft !== undefined}
        onOpenChange={(open) => {
          if (open) {
            history.reset();
            setShowPreview(false);
            setAttempted(false);
          }
          setDraft(open ? initialText : undefined);
        }}
      >
        <DialogTrigger asChild>
          <Button type="button" size="sm" variant="outline">
            <IconBraces aria-hidden="true" />
            变量与预览
          </Button>
        </DialogTrigger>
        <DialogContent className="max-w-5xl">
          <DialogTitle>漫画分镜提示词</DialogTitle>
          <DialogDescription>
            分镜正文必须包含核心话题列表和话题数量。预览用示例话题替换，生成时填入本次分析的结果。
            {!text.trim() && presetPrompt && " 当前显示内置正文，应用编辑后才会覆盖内置风格。"}
          </DialogDescription>
          <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(13rem,0.48fr)]">
            <div className="grid min-w-0 content-start gap-2 text-sm">
              <label htmlFor={`${id}-draft`}>分镜提示词正文</label>
              {error && (
                <p
                  id={`${id}-error`}
                  role="alert"
                  className="m-0 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive [overflow-wrap:anywhere]"
                >
                  <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  {error}
                </p>
              )}
              <textarea
                id={`${id}-draft`}
                ref={history.fieldRef}
                value={draft ?? ""}
                onChange={history.onChange}
                onCompositionStart={history.onCompositionStart}
                onKeyDown={history.onKeyDown}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? `${id}-error` : undefined}
                className="min-h-64 max-h-[55dvh] w-full resize-y rounded-xl border border-solid border-input bg-background p-3 font-mono text-sm leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive"
              />
            </div>
            <PromptVariablePanel
              variables={storyboardVariables}
              exampleFor={(key) => storyboardVariables[key].example}
              tokenFor={(key) => (legacyBraces ? `{${key}}` : "${" + key + "}")}
              onInsert={history.insert}
            />
          </div>
          {showPreview && (
            <section aria-labelledby={`${id}-preview`} className="grid min-w-0 gap-2">
              <h3 id={`${id}-preview`} className="m-0 text-sm font-medium">
                填入示例数据后的提示词
              </h3>
              <pre className="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-secondary-soft p-3 text-xs leading-relaxed">
                {storyboard.expanded ?? "此正文包含带格式修饰的旧变量，示例预览无法准确呈现。"}
                {storyboard.expanded === "" && "没有可预览的正文"}
              </pre>
            </section>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              aria-expanded={showPreview}
              onClick={() => setShowPreview(!showPreview)}
            >
              <IconEye aria-hidden="true" />
              {showPreview ? "收起预览" : "用示例数据预览"}
            </Button>
            <Button type="button" variant="outline" onClick={() => setDraft(undefined)}>
              取消
            </Button>
            <Button
              type="button"
              disabled={draft === initialText}
              onClick={() => {
                if (problem) {
                  setAttempted(true);
                  history.fieldRef.current?.focus();
                  return;
                }
                onChange(draft ?? "");
                setDraft(undefined);
              }}
            >
              应用到草稿
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
