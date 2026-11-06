import { useId, useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import { NativeSelect } from "../../../shared/ui/native-select";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { formatTokens } from "../../../shared/lib/formatters";
import { getPromptGroups, type PromptRecord } from "../model/promptRecords";

export function PromptsInspector({ prompts }: { prompts?: unknown }) {
  const groups = getPromptGroups(prompts);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selections, setSelections] = useState<Record<string, string>>({});
  const id = useId();
  const group = groups.find(({ key }) => key === selectedGroup) ?? groups[0];
  const record =
    group?.records.find(({ key }) => key === selections[group.key]) ?? group?.records.at(-1);
  if (!group || !record) return null;

  return (
    <details className="mt-5 text-sm">
      <summary className="cursor-pointer rounded-md py-2 font-medium focus-visible:outline-2 focus-visible:outline-ring">
        提示词与模型返回 · {groups.length} 个模块
      </summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label htmlFor={`${id}-module`} className="grid gap-1 text-muted-foreground">
          分析模块
          <NativeSelect
            id={`${id}-module`}
            value={group.key}
            onChange={(event) => setSelectedGroup(event.target.value)}
          >
            {groups.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
                {groups.filter((other) => other.label === item.label).length > 1
                  ? `（${item.key}）`
                  : ""}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label htmlFor={`${id}-record`} className="grid gap-1 text-muted-foreground">
          查看记录
          <NativeSelect
            id={`${id}-record`}
            value={record.key}
            onChange={(event) =>
              setSelections((previous) => ({ ...previous, [group.key]: event.target.value }))
            }
          >
            {group.records.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <PromptRecordContent key={`${group.key}/${record.key}`} record={record} />
    </details>
  );
}

function PromptRecordContent({ record }: { record: PromptRecord }) {
  const [copyResult, setCopyResult] = useState("");
  const { detail } = record;
  const sections = [
    { label: "系统提示词", text: detail.system_prompt },
    { label: "用户提示词", text: detail.prompt },
    { label: "模型返回", text: detail.completion },
  ];
  const metadata = [
    ["Provider", detail.provider_id],
    [
      "模型",
      detail.model && !detail.provider_id?.includes(detail.model) ? detail.model : undefined,
    ],
    ["类型", detail.provider_type],
    ["记录 Tokens", detail.tokens === undefined ? undefined : formatTokens(detail.tokens)],
    [
      "输入 Tokens",
      detail.prompt_tokens === undefined ? undefined : formatTokens(detail.prompt_tokens),
    ],
    [
      "输出 Tokens",
      detail.completion_tokens === undefined ? undefined : formatTokens(detail.completion_tokens),
    ],
    ["记录重试次数", detail.retry_count],
  ];
  const hasText = sections.some(({ text }) => text !== undefined);

  return (
    <div className="mt-4 space-y-4">
      <dl className="m-0 flex flex-wrap gap-x-5 gap-y-1 text-xs">
        {metadata
          .filter(([, value]) => value !== undefined)
          .map(([label, value]) => (
            <div key={label} className="flex min-w-0 gap-2">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="m-0 break-all font-mono">{value}</dd>
            </div>
          ))}
      </dl>
      {record.malformed ? (
        <p className="text-muted-foreground">这条记录的格式无法识别，可展开原始阶段记录查看。</p>
      ) : !hasText ? (
        <p className="text-muted-foreground">这次调用未保存提示词或返回正文。</p>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">保存的文本不代表已通过结果校验。</span>
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              const text = sections
                .filter((section) => section.text !== undefined)
                .map((section) => `=== ${section.label} ===\n${section.text}`)
                .join("\n\n");
              setCopyResult(
                (await copyToClipboard(text)) ? "已复制当前记录" : "复制失败，请选中文本复制",
              );
            }}
          >
            <IconCopy aria-hidden="true" />
            复制当前记录
          </Button>
        </div>
      )}
      {sections
        .filter(({ text }) => text !== undefined)
        .map(({ label, text }) => (
          <section key={label} aria-label={label}>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="font-medium">
                {label}
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {text?.length ?? 0} 字符
                </span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`复制${label}`}
                onClick={async () => {
                  setCopyResult(
                    (await copyToClipboard(text ?? ""))
                      ? `已复制${label}`
                      : "复制失败，请选中文本复制",
                  );
                }}
              >
                复制
              </Button>
            </div>
            <pre className="m-0 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-muted p-3 font-mono text-xs leading-relaxed text-foreground">
              {text === "" ? "（空文本）" : text}
            </pre>
          </section>
        ))}
      {copyResult && (
        <p role="status" className="m-0 text-sm text-muted-foreground">
          {copyResult}
        </p>
      )}
    </div>
  );
}
