import { LoadingState } from "../../../shared/ui/loading-state";
import { useEffect, useId, useRef, useState } from "react";
import type { ConnectedPlatform } from "../../../entities/task/api/taskApi";
import type { LLMProviderItem } from "../../../entities/trace/api/traceApi";
import {
  type ReportTemplateItem,
  formatTemplateOptions,
} from "../../../entities/report/model/templates";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";
import { Button } from "../../../shared/ui/button";
import { Input } from "../../../shared/ui/input";
import { NativeSelect } from "../../../shared/ui/native-select";

interface TriggerTaskModalProps {
  open: boolean;
  groupId: string;
  groupName: string;
  platform: string;
  providerId?: string;
  templateName?: string;
  submitting: boolean;
  connectedPlatforms?: ConnectedPlatform[];
  loadingPlatforms?: boolean;
  providers?: LLMProviderItem[];
  loadingProviders?: boolean;
  templates?: ReportTemplateItem[];
  loadingTemplates?: boolean;
  templatesError?: string;
  onRefreshTemplates?: () => void;
  onGroupIdChange: (val: string) => void;
  onGroupNameChange: (val: string) => void;
  onPlatformChange: (val: string) => void;
  onProviderChange?: (val: string) => void;
  onTemplateChange?: (val: string) => void;
  onClose: () => void;
  onSubmit: () => void | Promise<void>;
  optionsError?: string;
  onRefreshOptions?: () => void;
}

export function TriggerTaskModal({
  open,
  groupId,
  groupName,
  platform,
  providerId = "auto",
  templateName = "auto",
  submitting,
  connectedPlatforms = [],
  loadingPlatforms = false,
  providers = [],
  loadingProviders = false,
  templates = [],
  loadingTemplates = false,
  templatesError,
  onRefreshTemplates,
  optionsError,
  onRefreshOptions,
  onGroupIdChange,
  onGroupNameChange,
  onPlatformChange,
  onProviderChange,
  onTemplateChange,
  onClose,
  onSubmit,
}: TriggerTaskModalProps) {
  const id = useId();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const request = useRef<symbol | null>(null);
  const busy = pending || submitting;
  useEffect(() => {
    setError("");
    setPending(false);
    return () => {
      request.current = null;
    };
  }, [open]);
  const platformOptions = [
    { label: "自动识别平台", value: "auto" },
    ...(connectedPlatforms.length
      ? connectedPlatforms.map((item) => ({ label: item.label, value: item.id }))
      : [
          { label: "OneBot", value: "aiocqhttp" },
          { label: "QQ 官方机器人", value: "qq_official" },
          { label: "Telegram", value: "telegram" },
          { label: "Discord", value: "discord" },
        ]),
  ];
  const providerOptions = [
    { label: "使用默认模型", value: "auto" },
    ...providers.map((item) => ({
      label: item.label || `${item.name} (${item.id})`,
      value: item.id,
    })),
  ];
  const templateOptions = formatTemplateOptions(templates, true);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) onClose();
      }}
    >
      <DialogContent>
        <DialogTitle>发起分析</DialogTitle>
        <DialogDescription>选择目标群聊。本次模型和模板选择不会修改默认配置。</DialogDescription>
        {error && (
          <p role="alert" className="m-0 break-words text-sm text-destructive">
            {error}
          </p>
        )}
        {optionsError && (
          <div role="alert" className="space-y-2 text-sm">
            <p className="m-0">{optionsError}</p>
            <Button
              size="sm"
              variant="outline"
              disabled={busy || loadingPlatforms || loadingProviders}
              onClick={onRefreshOptions}
            >
              重新加载选项
            </Button>
          </div>
        )}
        <form
          className="grid gap-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy || request.current) return;
            const current = Symbol();
            request.current = current;
            setPending(true);
            setError("");
            try {
              await onSubmit();
            } catch (failure: unknown) {
              if (request.current === current)
                setError(
                  failure instanceof Error ? failure.message : "未能发起分析，请检查连接后重试。",
                );
            } finally {
              if (request.current === current) {
                request.current = null;
                setPending(false);
              }
            }
          }}
        >
          <div className="grid gap-2">
            <label htmlFor={`${id}-group`}>群号 / 会话标识</label>
            <Input
              id={`${id}-group`}
              required
              autoComplete="off"
              placeholder="输入目标群聊或会话的标识"
              value={groupId}
              disabled={busy}
              onChange={(event) => onGroupIdChange(event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label htmlFor={`${id}-name`}>群名称（选填）</label>
            <Input
              id={`${id}-name`}
              value={groupName}
              disabled={busy}
              onChange={(event) => onGroupNameChange(event.target.value)}
            />
          </div>
          {[
            {
              key: "platform",
              label: "平台",
              value: platform,
              options: platformOptions,
              loading: loadingPlatforms,
              change: onPlatformChange,
            },
            {
              key: "provider",
              label: "模型",
              value: providerId,
              options: providerOptions,
              loading: loadingProviders,
              change: onProviderChange,
            },
            {
              key: "template",
              label: "报告模板",
              value: templateName,
              options: templateOptions,
              loading: loadingTemplates,
              change: onTemplateChange,
            },
          ].map((field) => (
            <div key={field.key} className="grid gap-2">
              <label htmlFor={`${id}-${field.key}`}>{field.label}</label>
              <NativeSelect
                id={`${id}-${field.key}`}
                value={field.value}
                disabled={busy || field.loading}
                onChange={(event) => field.change?.(event.target.value)}
              >
                {!field.options.some((option) => option.value === field.value) && (
                  <option value={field.value}>
                    已选{field.label}：{field.value}
                  </option>
                )}
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </NativeSelect>
              {field.loading && (
                <LoadingState className="text-xs text-muted-foreground">
                  正在读取{field.label}…
                </LoadingState>
              )}
            </div>
          ))}
          {templatesError && (
            <div role="alert" className="space-y-2 text-sm">
              <p className="m-0">{templatesError}</p>
              <Button size="sm" variant="outline" disabled={busy} onClick={onRefreshTemplates}>
                重新加载模板
              </Button>
            </div>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="outline" disabled={busy} onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "正在提交…" : "开始分析"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
