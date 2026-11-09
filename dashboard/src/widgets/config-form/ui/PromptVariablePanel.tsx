import { IconPlus } from "@tabler/icons-react";
import type { PromptVariable } from "@/entities/config/model/types";
import { Button } from "@/shared/ui/button";

interface PromptVariablePanelProps {
  variables: Record<string, PromptVariable>;
  exampleFor: (key: string) => string;
  tokenFor?: (key: string) => string;
  onInsert?: (token: string) => void;
}

export function PromptVariablePanel({
  variables,
  exampleFor,
  tokenFor = (key) => "${" + key + "}",
  onInsert,
}: PromptVariablePanelProps) {
  return (
    <section aria-label="可用变量" className="grid min-w-0 content-start gap-2">
      <h3 className="m-0 text-sm font-medium">可用变量</h3>
      {onInsert && (
        <p className="m-0 text-xs text-muted-foreground">点击「插入」把变量放到正文光标处。</p>
      )}
      {Object.entries(variables).map(([key, variable]) => {
        const token = tokenFor(key);
        return (
          <div key={key} className="grid min-w-0 gap-1 rounded-xl bg-secondary-soft p-2">
            <div className="flex flex-wrap items-center justify-between gap-1 text-sm">
              <span>{variable.label}</span>
              <span className="text-xs text-muted-foreground">
                {variable.required ? "必填" : "可选"}
              </span>
            </div>
            <p className="m-0 text-xs text-muted-foreground">{variable.description}</p>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">查看变量示例</summary>
              <pre className="mb-0 max-h-32 overflow-auto whitespace-pre-wrap break-words">
                {exampleFor(key)}
              </pre>
            </details>
            {onInsert ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-auto min-h-8 justify-start whitespace-normal text-xs"
                title={`在正文光标处插入「${variable.label}」，有选中文字时将替换选区`}
                onClick={() => onInsert(token)}
              >
                <IconPlus aria-hidden="true" />
                插入 <code className="break-all">{token}</code>
              </Button>
            ) : (
              <code className="break-all text-xs">{token}</code>
            )}
          </div>
        );
      })}
    </section>
  );
}
