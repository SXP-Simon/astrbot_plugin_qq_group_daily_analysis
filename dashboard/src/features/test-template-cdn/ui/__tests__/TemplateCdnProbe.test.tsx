import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { testTemplateCdn } from "../../../../entities/config/api/configApi";
import type { TemplateCdnProbe as ProbeResult } from "../../../../entities/config/model/cdnProbe";
import { TemplateCdnProbe } from "../TemplateCdnProbe";

vi.mock("../../../../entities/config/api/configApi", () => ({ testTemplateCdn: vi.fn() }));

const result: ProbeResult = {
  base_url: "https://example.com",
  usable: true,
  checks: [
    { id: "maria-png", label: "装饰图片", description: "Maria 模板的蔷薇图片", kind: "gh", url: "https://example.com/gh/sample.png", success: true, status_code: 200, elapsed_ms: 123, bytes_received: 1024, error: null },
    { id: "npm-css", label: "npm 兼容性", description: "额外检查 normalize.css；当前内置模板没有使用它", kind: "npm", url: "https://example.com/npm/sample.css", success: true, status_code: 200, elapsed_ms: 456, bytes_received: 2048, error: null },
  ],
};

describe("模板 CDN 检测", () => {
  beforeEach(() => vi.resetAllMocks());

  it("检测当前输入并展示两项资源结果", async () => {
    vi.mocked(testTemplateCdn).mockResolvedValue(result);
    render(<TemplateCdnProbe baseUrl=" https://example.com/ " />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    expect(testTemplateCdn).toHaveBeenCalledWith(" https://example.com/ ");
    expect(await screen.findByText("测试文件都能加载，可以保存后试生成报告了")).toBeInTheDocument();
    expect(screen.getByText("装饰图片：加载成功")).toBeInTheDocument();
    expect(screen.getByText("npm 兼容性：加载成功")).toBeInTheDocument();
    expect(screen.getByText("额外检查 normalize.css；当前内置模板没有使用它")).toBeInTheDocument();
    expect(screen.getAllByText("查看下载详情")).toHaveLength(2);
  });

  it("单项失败时给出原因且不宣称可用", async () => {
    vi.mocked(testTemplateCdn).mockResolvedValue({
      ...result, usable: false,
      checks: [result.checks[0], { ...result.checks[1], success: false, status_code: 404, error: "资源请求失败：HTTP 404" }],
    });
    render(<TemplateCdnProbe baseUrl="https://example.com" />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    expect(await screen.findByText("1 / 2 个文件加载成功，请看看下面哪些没有加载出来")).toBeInTheDocument();
    expect(screen.getByText("资源请求失败：HTTP 404")).toBeInTheDocument();
  });

  it("输入改变后清除结果并忽略旧请求的迟到响应", async () => {
    let resolve!: (value: ProbeResult) => void;
    vi.mocked(testTemplateCdn).mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = render(<TemplateCdnProbe baseUrl="https://example.com" />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    view.rerender(<TemplateCdnProbe baseUrl="https://new.example.com" />);
    await act(async () => resolve(result));
    expect(screen.queryByText("测试文件都能加载，可以保存后试生成报告了")).not.toBeInTheDocument();
    vi.mocked(testTemplateCdn).mockRejectedValue(new Error("下载超时"));
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    await waitFor(() => expect(testTemplateCdn).toHaveBeenLastCalledWith("https://new.example.com"));
    expect(await screen.findByText("下载超时")).toBeInTheDocument();
    view.rerender(<TemplateCdnProbe baseUrl="" />);
    expect(screen.queryByText("下载超时")).not.toBeInTheDocument();
  });
});
