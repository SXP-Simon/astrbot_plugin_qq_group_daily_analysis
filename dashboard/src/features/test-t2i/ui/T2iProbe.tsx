import { IconCheck, IconAlertCircle, IconPhoto, IconLoader2 } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import { SearchSelect } from "../../../shared/ui/search-select";
import type { T2iProbeInput } from "../../../entities/config/model/t2iProbe";
import { useT2iProbe } from "../model/useT2iProbe";

export function T2iProbe({ input }: { input: T2iProbeInput }) {
  const { loading, result, error, run, groupOptions, groupKey, setGroupKey, groupsError } =
    useT2iProbe(input);
  const hostService = input.render_service === "astrbot";
  return (
    <section aria-label="测试渲染" className="mt-3 min-w-0 space-y-3">
      {hostService && (
        <>
          <p className="m-0 text-sm">测试使用的 AstrBot 配置</p>
          <SearchSelect
            label="测试使用的 AstrBot 配置"
            value={groupKey}
            onChange={setGroupKey}
            options={groupOptions}
          />
          {groupsError && (
            <p role="status" className="m-0 text-sm text-warning">
              {groupsError}
            </p>
          )}
        </>
      )}
      <Button
        variant="outline"
        className="border-info/20 bg-info/5 text-info hover:bg-info/10"
        disabled={loading}
        onClick={() => void run()}
      >
        {loading ? (
          <IconLoader2 aria-hidden="true" className="animate-spin" />
        ) : (
          <IconPhoto aria-hidden="true" />
        )}
        {loading ? "正在生成测试图…" : "测试渲染"}
      </Button>
      <p className="m-0 text-sm text-muted-foreground">
        {input.render_service === "typst"
          ? "测试插件数据目录中的字体和 Typst 独立编译器，不调用 AstrBot 渲染服务。"
          : hostService
            ? "无需保存即可测试 T2I（文字转图片）服务。未绑定配置的群使用默认配置；旧版 AstrBot 可能只支持默认配置。"
            : "无需保存即可测试当前 T2I（文字转图片）服务地址和 Token。"}
        {input.render_service === "typst"
          ? "不会下载角色素材、调用大模型或发到群里。"
          : "测试检查 T2I 服务是否可用，不检查模板图片和字体；不会调用大模型或发到群里。"}
      </p>
      {error && (
        <p
          role="alert"
          className="m-0 flex items-start gap-2 rounded-xl bg-destructive/10 p-3 text-sm text-destructive"
        >
          <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span className="min-w-0 break-words">{error}</span>
        </p>
      )}
      {result && (
        <>
          <p
            role="status"
            className="m-0 flex items-center gap-2 rounded-xl bg-success/10 p-3 text-sm text-success"
          >
            <IconCheck aria-hidden="true" className="size-4 shrink-0" />
            {`测试图片已生成，用时 ${(result.elapsed_ms / 1000).toFixed(2)} 秒`}
          </p>
          <img
            src={result.image_data_url}
            alt="T2I 测试图片"
            className="block h-auto max-w-full rounded-lg"
          />
        </>
      )}
    </section>
  );
}
