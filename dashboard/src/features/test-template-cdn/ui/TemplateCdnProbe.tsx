import { Alert, Button, Typography } from "antd";
import { useTemplateCdnProbe } from "../model/useTemplateCdnProbe";

export function TemplateCdnProbe({ baseUrl }: { baseUrl: string }) {
  const { loading, result, error, run } = useTemplateCdnProbe(baseUrl);
  const passed = result?.checks.filter((check) => check.success).length ?? 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div>
        <Button onClick={() => void run()} loading={loading}>
          {loading ? "正在检查链接…" : "检测可用性"}
        </Button>
      </div>
      <Typography.Text type="secondary">
        不用先保存，直接测试上面填写的地址；留空则测试默认地址。
      </Typography.Text>
      {error && <Alert type="error" showIcon message={error} />}
      {result && (
        <Alert
          type={result.usable ? "success" : "warning"}
          showIcon
          message={result.usable
            ? "测试链接都能访问，可以保存后试生成报告了"
            : `${passed} / ${result.checks.length} 个链接确认可访问，其他结果请看下方说明`}
          description={
            <div style={{ overflowWrap: "anywhere" }}>
              <div>这次测试的地址：{result.base_url}</div>
              {result.checks.map((check) => (
                <div key={check.id} style={{ marginTop: 12 }}>
                  <strong>{check.label}：{check.success ? "可访问" : "未确认可访问"}</strong>
                  <div>{check.description}</div>
                  {check.error && <div>{check.error}</div>}
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ cursor: "pointer" }}>查看检测详情</summary>
                    <div>
                      用时 {(check.elapsed_ms / 1000).toFixed(2)} 秒
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
