import { Alert, Button, Typography } from "antd";
import { useTemplateCdnProbe } from "../model/useTemplateCdnProbe";

export function TemplateCdnProbe({ baseUrl }: { baseUrl: string }) {
  const { loading, result, error, run } = useTemplateCdnProbe(baseUrl);
  const passed = result?.checks.filter((check) => check.success).length ?? 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div>
        <Button onClick={() => void run()} loading={loading}>
          {loading ? "正在试着加载图片和字体…" : "检测可用性"}
        </Button>
      </div>
      <Typography.Text type="secondary">
        不用先保存，直接测试上面填写的地址；留空则测试默认地址。
        会下载几张模板图片和一份约 8 MB 的字体，另外检查 npm 是否可用，可能需要几十秒。
      </Typography.Text>
      {error && <Alert type="error" showIcon message={error} />}
      {result && (
        <Alert
          type={result.usable ? "success" : "warning"}
          showIcon
          message={result.usable
            ? "测试文件都能加载，可以保存后试生成报告了"
            : `${passed} / ${result.checks.length} 个文件加载成功，请看看下面哪些没有加载出来`}
          description={
            <div style={{ overflowWrap: "anywhere" }}>
              <div>这次测试的地址：{result.base_url}</div>
              {result.checks.map((check) => (
                <div key={check.id} style={{ marginTop: 12 }}>
                  <strong>{check.label}：{check.success ? "加载成功" : "未能加载"}</strong>
                  <div>{check.description}</div>
                  {check.error && <div>{check.error}</div>}
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ cursor: "pointer" }}>查看下载详情</summary>
                    <div>
                      用时 {(check.elapsed_ms / 1000).toFixed(2)} 秒 · 已接收 {check.bytes_received >= 1024 * 1024
                        ? `${(check.bytes_received / (1024 * 1024)).toFixed(2)} MB`
                        : `${(check.bytes_received / 1024).toFixed(1)} KB`}
                      {check.status_code !== null && ` · HTTP ${check.status_code}`}
                    </div>
                    <a href={check.url} target="_blank" rel="noreferrer">{check.url}</a>
                  </details>
                </div>
              ))}
              <div style={{ marginTop: 12 }}>
                这里测试的是机器人所在服务器。若你用的是远程图片渲染服务，保存后再生成一份报告看看。
                检测不会自动保存配置。
              </div>
            </div>
          }
        />
      )}
    </div>
  );
}
