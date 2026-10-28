import { Alert, Button, Image, Select, Space, Typography } from "antd";
import type { T2iProbeInput } from "../../../entities/config/model/t2iProbe";
import { useT2iProbe } from "../model/useT2iProbe";

export function T2iProbe({ input }: { input: T2iProbeInput }) {
  const { loading, result, error, run, groupOptions, groupKey, setGroupKey, groupsError } = useT2iProbe(input);
  const hostService = input.render_service === "astrbot";
  return (
    <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
      {hostService && <>
        <Typography.Text>测试所用配置</Typography.Text>
        <Select aria-label="测试所用配置" value={groupKey} onChange={setGroupKey}
          options={groupOptions} style={{ width: "100%" }} />
        {groupsError && <Typography.Text type="secondary">{groupsError}</Typography.Text>}
      </>}
      <Button loading={loading} onClick={() => void run()}>
        {loading ? "正在生成测试图…" : "测试渲染"}
      </Button>
      <Typography.Text type="secondary">
        {hostService
          ? "通过 AstrBot 生成一张测试图，可选择默认配置或列表中群聊绑定的配置；未绑定时跟随默认配置，旧版 AstrBot 可能只能使用默认配置。使用当前超时，不用先保存方案。"
          : "不用先保存，使用当前地址、Token 和超时设置生成一张小图。"}
        不调用大模型、不发送群消息，图片只在这里展示。
        这项测试不加载外链资源，模板字体和图片是否完整，请再试生成报告。
      </Typography.Text>
      {error && <Alert type="error" showIcon message={error} />}
      {result && <>
        <Alert type="success" showIcon message={`测试图片已生成，用时 ${(result.elapsed_ms / 1000).toFixed(2)} 秒`} />
        <Image src={result.image_data_url} alt="T2I 测试图片" preview={false} style={{ maxWidth: "100%" }} />
      </>}
    </Space>
  );
}
