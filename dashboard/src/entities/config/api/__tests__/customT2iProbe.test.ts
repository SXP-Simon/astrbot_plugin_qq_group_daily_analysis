import { beforeEach, expect, it, vi } from "vitest";
import { apiPost } from "../../../../shared/api/bridge";
import { testCustomT2i } from "../configApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(), apiPost: vi.fn(),
}));
beforeEach(() => vi.resetAllMocks());
const result = { image_data_url: "data:image/png;base64,aGVsbG8=", elapsed_ms: 150 };

it("规范化服务地址和 Token，复用默认超时，解析宿主双层信封", async () => {
  vi.mocked(apiPost).mockResolvedValue({ status: "ok", data: { status: "ok", data: result } });
  expect(await testCustomT2i({ service_endpoint: " http://127.0.0.1:8999/text2img/generate/ ", service_token: " secret " })).toEqual(result);
  expect(apiPost).toHaveBeenCalledWith("config/test-custom-t2i", {
    service_endpoint: "http://127.0.0.1:8999/text2img", service_token: "secret", timeout: 20000, request_timeout: 40000,
  });
});

it.each([{ service_endpoint: "bad" }, { service_token: "secret\n" }, { timeout: 999 }, { request_timeout: true }])("请求前拒绝无效草稿：%j", async (input) => {
  await expect(testCustomT2i(input)).rejects.toThrow();
  expect(apiPost).not.toHaveBeenCalled();
});

it.each([
  { status: "error", message: "服务不可用" },
  { status: "ok", data: { status: "error", message: "服务不可用", data: null } },
  { status: "error", message: "服务不可用", data: result },
])("不能把错误信封当成功：%j", async (response) => {
  vi.mocked(apiPost).mockResolvedValue(response);
  await expect(testCustomT2i({})).rejects.toThrow("服务不可用");
});

it.each([null, { elapsed_ms: -1, image_data_url: result.image_data_url }, { elapsed_ms: 1, image_data_url: "https://example.com/image.png" }, { elapsed_ms: 1, image_data_url: "data:image/svg+xml;base64,aGVsbG8=" }])("拒绝缺失或异常的图片响应：%j", async (data) => {
  vi.mocked(apiPost).mockResolvedValue({ status: "ok", data });
  await expect(testCustomT2i({})).rejects.toThrow();
});
