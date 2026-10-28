import { Alert, Button, Image, Select, Space, Typography } from "antd";
import type { T2iProbeInput } from "../../../entities/config/model/t2iProbe";
import { useT2iProbe } from "../model/useT2iProbe";

export function T2iProbe({ input }: { input: T2iProbeInput }) {
  const { loading, result, error, run, groupOptions, groupKey, setGroupKey, groupsError } = useT2iProbe(input);
  const hostService = input.render_service === "astrbot";
  return (
    <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
      {hostService && <>
        <Typography.Text>测试使用的 AstrBot 配置</Typography.Text>
        <Select aria-label="测试使用的 AstrBot 配置" value={groupKey} onChange={setGroupKey}
          options={groupOptions} style={{ width: "100%" }} />
        {groupsError && <Typography.Text type="secondary">{groupsError}</Typography.Text>}
      </>}
      <Button loading={loading} onClick={() => void run()}>
        {loading ? "正在生成测试图…" : "测试渲染"}
      </Button>
      <Typography.Text type="secondary">
        {hostService
          ? "无需保存即可测试图片服务。未绑定配置的群使用默认配置；旧版 AstrBot 可能只支持默认配置。"
          : "无需保存即可测试当前服务地址和 Token。"}
        测试不调用大模型，也不会发到群里。模板素材请通过报告确认。
      </Typography.Text>
      {error && <Alert type="error" showIcon message={error} />}
      {result && <>
        <Alert type="success" showIcon message={`测试图片已生成，用时 ${(result.elapsed_ms / 1000).toFixed(2)} 秒`} />
        <Image src={result.image_data_url} alt="T2I 测试图片" preview={false} style={{ maxWidth: "100%" }} />
      </>}
    </Space>
  );
}
