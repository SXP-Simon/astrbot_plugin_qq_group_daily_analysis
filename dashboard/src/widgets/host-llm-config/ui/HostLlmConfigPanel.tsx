import {
  IconArrowRight,
  IconRefresh,
  IconLock,
  IconHierarchy,
  IconRoute,
  IconBrain,
  IconArrowBackUp,
  IconSettings,
  IconInfoCircle,
} from "@tabler/icons-react";
import { Button } from "@/shared/ui/button";
import { SearchSelect } from "@/shared/ui/search-select";
import { ModelIcon } from "@/entities/config/ui/ModelIcon";
import { PlatformIcon } from "@/entities/group/ui/PlatformIcon";
import { useHostLlmConfig } from "@/widgets/host-llm-config/model/useHostLlmConfig";

export function HostLlmConfigPanel({
  draft,
  dirty,
}: {
  draft: Record<string, unknown>;
  dirty: boolean;
}) {
  const vm = useHostLlmConfig(draft);
  const primary = vm.data?.providers.find((item) => item.id === vm.data?.primary_id);
  return (
    <section
      aria-label="宿主模型与调用顺序"
      className="min-w-0 space-y-6 rounded-2xl border border-border bg-card p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3 className="m-0 flex flex-wrap items-center gap-2 text-base font-medium">
            <IconHierarchy aria-hidden="true" className="size-5 text-primary-ink" />
            AstrBot 模型继承{" "}
            <span className="flex items-center gap-1 rounded-md bg-card px-2 py-0.5 text-xs text-muted-foreground">
              <IconLock className="size-3" aria-hidden="true" />
              宿主只读
            </span>
          </h3>
          <p className="m-0 text-sm text-muted-foreground">
            查看宿主模型配置，并预览下方插件设置对应的调用顺序。
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={vm.refresh} disabled={vm.loading}>
          <IconRefresh aria-hidden="true" />
          刷新宿主信息
        </Button>
      </div>
      <div>
        <label htmlFor="host-llm-session" className="mb-1.5 block text-sm font-medium">
          查看范围
        </label>
        <SearchSelect
          id="host-llm-session"
          label="查看范围"
          value={vm.selection}
          onChange={vm.setSelection}
          virtual
          options={[
            {
              value: "",
              label: "宿主默认配置",
              icon: <IconSettings aria-hidden="true" className="size-5" />,
            },
            ...vm.options.map((option) => ({
              value: option.key,
              label: option.label,
              icon: <PlatformIcon platform={option.group.platform} />,
            })),
          ]}
        />
        <p className="mb-0 mt-1.5 text-xs text-muted-foreground">
          群列表来自已有分析记录；不同机器人实例或群会话可能使用不同模型。查看范围不会修改任务目标。
        </p>
      </div>
      {vm.groupError && (
        <p role="status" className="text-sm text-warning">
          {vm.groupError}
        </p>
      )}
      {vm.loading && (
        <p role="status" className="text-sm text-muted-foreground">
          正在读取宿主模型配置…
        </p>
      )}
      {vm.error && (
        <p role="alert" className="text-sm text-destructive">
          {vm.error}
        </p>
      )}
      {vm.data && vm.chains && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="min-w-0 space-y-3 rounded-xl border border-primary-line bg-primary-soft p-4">
              <p className="m-0 flex items-center gap-2 text-xs text-muted-foreground">
                <IconBrain aria-hidden="true" className="size-4" />
                宿主当前主模型
              </p>
              <p className="m-0 flex items-center gap-3 text-sm font-medium">
                <ModelIcon {...primary} className="size-7" />
                <span className="min-w-0 break-words">
                  {primary?.name || vm.data.primary_id || "未取得主模型"}
                </span>
              </p>
              {primary && (
                <p className="mb-0 mt-1 break-all text-xs text-muted-foreground">
                  {primary.id}
                  {primary.model ? ` · ${primary.model}` : ""}
                  {!primary.available ? " · 当前不可用" : ""}
                </p>
              )}
              {!vm.data.primary_id && (
                <p className="mb-0 mt-1 text-xs text-muted-foreground">
                  插件将尝试首个已加载的对话模型。
                </p>
              )}
            </div>
            <div className="min-w-0 rounded-xl border border-border bg-background p-4">
              <p className="mb-3 mt-0 flex items-center gap-2 text-xs text-muted-foreground">
                <IconArrowBackUp aria-hidden="true" className="size-4" />
                宿主回退模型 · 按配置顺序去重
              </p>
              {vm.data.fallback_ids.length ? (
                <ol className="m-0 list-none space-y-3 p-0 text-sm">
                  {vm.data.fallback_ids.map((id, index) => {
                    const provider = vm.data?.providers.find((item) => item.id === id);
                    return (
                      <li key={id} className="flex min-w-0 items-start gap-2.5">
                        <span
                          aria-hidden="true"
                          className="text-xs leading-5 text-muted-foreground"
                        >
                          {index + 1}.
                        </span>
                        <ModelIcon {...provider} />
                        <div className="min-w-0 break-words">
                          <span>{provider?.name || id}</span>
                          <span className="ml-1 text-xs text-muted-foreground">
                            {provider?.name !== id ? `（${id}）` : ""}
                            {!provider?.available ? " · 不可用，将跳过" : ""}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="m-0 text-sm text-muted-foreground">未配置回退模型</p>
              )}
            </div>
          </div>
          <div className="space-y-3">
            <div>
              <h4 className="m-0 flex flex-wrap items-center gap-2 text-sm font-medium">
                <IconRoute aria-hidden="true" className="size-4 text-primary-ink" />
                插件调用顺序 {dirty && <span className="ml-1 text-warning">· 未保存的预览</span>}
              </h4>
              <p className="mb-0 mt-1 text-xs text-muted-foreground">
                {vm.chains.inherit
                  ? "主 LLM 留空，继承所选范围的宿主回退列表。"
                  : "已指定插件主 LLM，不追加宿主回退列表。"}
                {dirty ? " 保存插件配置后生效。" : " 按已保存的插件设置展示。"}
              </p>
            </div>
            <dl className="m-0 divide-y divide-border rounded-xl border border-border bg-background px-4">
              {vm.chains.rows.map((row) => (
                <div
                  key={row.label}
                  className="grid items-start gap-3 py-4 xl:grid-cols-[6rem_minmax(0,1fr)]"
                >
                  <dt className="text-sm text-muted-foreground">{row.label}</dt>
                  <dd className="m-0 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {row.models.length ? (
                        row.models.map((model, index) => (
                          <span
                            key={model.id}
                            className="inline-flex max-w-full items-center gap-1.5"
                          >
                            {index > 0 && (
                              <IconArrowRight
                                aria-label="失败后尝试"
                                className="size-3.5 shrink-0 text-muted-foreground"
                              />
                            )}
                            <span
                              title={`${model.id}${model.model ? ` · ${model.model}` : ""}`}
                              className="inline-flex min-w-0 items-center gap-2 rounded-lg border border-secondary-line bg-secondary-soft px-2.5 py-2 text-xs"
                            >
                              <ModelIcon {...model} className="size-4" />
                              <span className="min-w-0 break-words">{model.name}</span>
                            </span>
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-warning">没有可用的对话模型</span>
                      )}
                    </div>
                    {row.missing.length > 0 && (
                      <p className="mb-0 mt-1 text-xs text-warning">
                        指定模型不可用：{row.missing.join("、")}；按现有规则继续选择默认模型。
                      </p>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="m-0 flex items-start gap-2 rounded-xl bg-secondary-soft p-4 text-xs leading-6 text-muted-foreground">
              <IconInfoCircle aria-hidden="true" className="mt-1 size-4 shrink-0" />
              <span>
                每个模型按插件设置尝试，失败后切换，成功即停止；重复模型不重复加入。此处展示模型选择规则，不会调用模型或检测余额。WebUI
                临时指定模型时不追加宿主回退列表。修改宿主模型及备用顺序，请前往 AstrBot
                的对应配置。
              </span>
            </p>
          </div>
        </>
      )}
    </section>
  );
}
