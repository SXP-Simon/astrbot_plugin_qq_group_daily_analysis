import { useId } from "react";
import { IconRefresh } from "@tabler/icons-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../../shared/ui/dialog";
import { Button } from "../../../shared/ui/button";
import { NativeSelect } from "../../../shared/ui/native-select";
import { useResumeOptions } from "../model/useResumeOptions";

interface ResumeTaskModalProps {
  open: boolean;
  loading: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: (selectedProvider?: string, selectedTemplate?: string) => void;
}

export function ResumeTaskModal({
  open,
  loading,
  error,
  onCancel,
  onConfirm,
}: ResumeTaskModalProps) {
  const vm = useResumeOptions(open);
  const id = useId();
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !loading) onCancel();
      }}
    >
      <DialogContent>
        <DialogTitle>继续分析</DialogTitle>
        <DialogDescription>
          优先复用已保存的结果，补齐未完成的分析。快照缺失时会重新拉取消息，可能产生新的模型消耗。
        </DialogDescription>
        {error && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {error}
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!loading && vm.canConfirm)
              onConfirm(
                vm.selectedProvider === "auto" ? undefined : vm.selectedProvider,
                vm.selectedTemplate === "auto" ? undefined : vm.selectedTemplate,
              );
          }}
          className="grid gap-5"
        >
          <div className="grid gap-2">
            <label htmlFor={`${id}-provider`}>模型</label>
            <NativeSelect
              id={`${id}-provider`}
              value={vm.selectedProvider}
              disabled={loading || vm.loadingProviders}
              onChange={(event) => vm.setSelectedProvider(event.target.value)}
            >
              <option value="auto">使用原配置</option>
              {vm.providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label || `${provider.name} (${provider.id})`}
                </option>
              ))}
            </NativeSelect>
            {vm.loadingProviders && (
              <span role="status" className="text-sm text-muted-foreground">
                正在加载模型…
              </span>
            )}
            {vm.providerError && (
              <div role="alert" className="text-sm text-destructive">
                {vm.providerError}
                <Button variant="link" size="sm" onClick={vm.retryProviders} disabled={loading}>
                  重试模型列表
                </Button>
              </div>
            )}
          </div>
          <div className="grid gap-2">
            <label htmlFor={`${id}-template`}>报告模板</label>
            <NativeSelect
              id={`${id}-template`}
              value={vm.selectedTemplate}
              disabled={loading || vm.loadingTemplates}
              onChange={(event) => vm.setSelectedTemplate(event.target.value)}
            >
              {vm.templateOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
            {vm.loadingTemplates && (
              <span role="status" className="text-sm text-muted-foreground">
                正在加载模板…
              </span>
            )}
            {vm.templateError && (
              <div role="alert" className="text-sm text-destructive">
                {vm.templateError}
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => void vm.retryTemplates()}
                  disabled={loading}
                >
                  重试模板列表
                </Button>
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel} disabled={loading}>
              取消
            </Button>
            <Button type="submit" disabled={loading || !vm.canConfirm}>
              <IconRefresh aria-hidden="true" className={loading ? "animate-spin" : undefined} />
              {loading ? "正在提交…" : "开始续跑"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
