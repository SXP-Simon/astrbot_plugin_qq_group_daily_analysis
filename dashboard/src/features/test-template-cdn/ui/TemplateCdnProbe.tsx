import { IconAlertCircle, IconCheck, IconLoader2, IconPlugConnected } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import { useTemplateCdnProbe } from "../model/useTemplateCdnProbe";

export function TemplateCdnProbe({ baseUrl }: { baseUrl: string }) {
  const { loading, result, error, run } = useTemplateCdnProbe(baseUrl);
  const passed = result?.checks.filter((check) => check.success).length ?? 0;
  return (
    <section aria-label="CDN 可用性检测" className="min-w-0 space-y-3">
      <Button
        variant="outline"
        className="border-info/20 bg-info/5 text-info hover:bg-info/10"
        onClick={() => void run()}
        disabled={loading}
      >
        {loading ? (
          <IconLoader2 aria-hidden="true" className="animate-spin" />
        ) : (
          <IconPlugConnected aria-hidden="true" />
        )}
        {loading ? "正在检查链接…" : "检测可用性"}
      </Button>
      <p className="m-0 text-sm text-muted-foreground">
        不用先保存，直接测试上面填写的地址；留空则测试默认地址。
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
        <div className="space-y-3 text-sm [overflow-wrap:anywhere]">
          <p
            role="status"
            className={`m-0 flex items-start gap-2 rounded-xl p-3 ${result.usable ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}
          >
            {result.usable ? (
              <IconCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            ) : (
              <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            )}
            <span>
              {result.usable
                ? "测试链接都能访问，可以保存后试生成报告了"
                : `${passed} / ${result.checks.length} 个链接确认可访问，其他结果请看下方说明`}
            </span>
          </p>
          <p className="m-0 text-muted-foreground">
            这次测试的地址：<span className="font-mono">{result.base_url}</span>
          </p>
          <ul aria-label="资源检测结果" className="m-0 list-none divide-y divide-border p-0">
            {result.checks.map((check) => (
              <li key={check.id} className="space-y-1 py-3">
                <p
                  className={`m-0 flex items-start gap-2 font-medium ${check.success ? "text-success" : "text-warning"}`}
                >
                  {check.success ? (
                    <IconCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  ) : (
                    <IconAlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  )}
                  <span>
                    {check.label}：{check.success ? "可访问" : "未确认可访问"}
                  </span>
                </p>
                <p className="m-0 text-muted-foreground">{check.description}</p>
                {check.error && <p className="m-0">{check.error}</p>}
                <details>
                  <summary className="w-fit cursor-pointer rounded-sm py-1 text-info focus-visible:outline-2 focus-visible:outline-ring">
                    查看检测详情
                  </summary>
                  <p className="m-0 py-1 text-muted-foreground">
                    用时 {(check.elapsed_ms / 1000).toFixed(2)} 秒
                    {check.status_code !== null && ` · HTTP ${check.status_code}`}
                  </p>
                  <a
                    className="font-mono text-xs text-info underline underline-offset-4"
                    href={check.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {check.url}
                  </a>
                </details>
              </li>
            ))}
          </ul>
          <p className="m-0 text-muted-foreground">
            这里测试的是机器人所在服务器。若你用的是远程图片渲染服务，保存后再生成一份报告看看。
            检测不会自动保存配置。
          </p>
        </div>
      )}
    </section>
  );
}
