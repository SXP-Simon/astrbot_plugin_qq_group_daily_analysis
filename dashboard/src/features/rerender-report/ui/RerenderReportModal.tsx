import { LoadingState } from "../../../shared/ui/loading-state";
import { useId } from "react";
import type { ReportItem } from "../../../entities/report/model/types";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";
import { Button } from "../../../shared/ui/button";
import { NativeSelect } from "../../../shared/ui/native-select";
import { useRerenderReport } from "../model/useRerenderReport";

interface RerenderReportModalProps {
  open: boolean;
  report: ReportItem | null;
  onClose: () => void;
  onSuccess: () => void | Promise<unknown>;
}

export function RerenderReportModal({
  open,
  report,
  onClose,
  onSuccess,
}: RerenderReportModalProps) {
  const vm = useRerenderReport(open, report, onClose, onSuccess);
  const id = useId();
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) vm.close();
      }}
    >
      <DialogContent>
        <DialogTitle>换模板重绘</DialogTitle>
        <DialogDescription>
          复用已保存的分析结果，不重新调用分析模型。新报告保存在插件中，不发送到群聊。
        </DialogDescription>
        <div className="min-w-0 space-y-1 text-sm">
          <p className="m-0">{report?.group_name || report?.group_id || "未记录群聊"}</p>
          <p className="m-0 break-all font-mono text-xs text-muted-foreground">
            {report?.filename}
          </p>
        </div>
        {!report?.group_id?.trim() && (
          <p role="alert" className="m-0 text-sm text-destructive">
            这份报告没有群聊记录，暂时无法重绘。仍可预览或下载原文件。
          </p>
        )}
        {vm.submitError && (
          <p role="alert" className="m-0 whitespace-pre-wrap break-words text-sm text-destructive">
            {vm.submitError}
          </p>
        )}
        <form
          aria-label="重绘报告"
          className="grid gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            void vm.submit();
          }}
        >
          <div className="grid gap-2">
            <label htmlFor={`${id}-format`}>输出格式</label>
            <NativeSelect
              id={`${id}-format`}
              value={vm.renderFormat}
              disabled={vm.submitting}
              onChange={(event) =>
                vm.setRenderFormat(event.target.value === "html" ? "html" : "image")
              }
            >
              <option value="image">图片报告</option>
              <option value="html">HTML 网页</option>
            </NativeSelect>
          </div>
          <div className="grid gap-2">
            <label htmlFor={`${id}-template`}>报告模板</label>
            <NativeSelect
              id={`${id}-template`}
              value={vm.templateName}
              disabled={!vm.templatesReady || vm.submitting}
              onChange={(event) => vm.setTemplateName(event.target.value)}
            >
              {!vm.validTemplate && (
                <option value={vm.templateName}>
                  {vm.templateName
                    ? `原选择：${vm.templateName}（当前格式不可用）`
                    : "请选择可用模板"}
                </option>
              )}
              {vm.templateOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
            {vm.loadingTemplates && (
              <LoadingState className="text-sm text-muted-foreground">正在读取模板…</LoadingState>
            )}
            {vm.templatesReady && !vm.templateOptions.length && (
              <p role="status" className="m-0 text-sm text-muted-foreground">
                没有支持该格式的模板，请切换输出格式。
              </p>
            )}
            {vm.templatesReady && !!vm.templateOptions.length && !vm.validTemplate && (
              <p role="alert" className="m-0 text-sm text-destructive">
                原选模板不支持当前格式，请重新选择。
              </p>
            )}
            {vm.templatesError && (
              <div role="alert" className="space-y-2 text-sm">
                <p className="m-0">{vm.templatesError}</p>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={vm.submitting}
                  onClick={() => void vm.refreshTemplates()}
                >
                  重新加载模板
                </Button>
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" disabled={vm.submitting} onClick={vm.close}>
              取消
            </Button>
            <Button type="submit" disabled={!vm.canSubmit}>
              {vm.submitting ? "正在生成…" : "生成新报告"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
