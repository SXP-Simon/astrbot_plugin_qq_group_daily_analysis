import { Alert, Button, Image, Space, Typography } from "antd";
import type { CustomT2iProbeInput } from "../../../entities/config/model/customT2iProbe";
import { useCustomT2iProbe } from "../model/useCustomT2iProbe";

export function CustomT2iProbe({ input }: { input: CustomT2iProbeInput }) {
  const { loading, result, error, run } = useCustomT2iProbe(input);
  return (
    <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
      <Button loading={loading} onClick={() => void run()}>
        {loading ? "正在生成测试图…" : "测试渲染"}
      </Button>
      <Typography.Text type="secondary">
        不用先保存，使用当前地址、Token 和超时设置生成一张小图，只在这里展示。
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
