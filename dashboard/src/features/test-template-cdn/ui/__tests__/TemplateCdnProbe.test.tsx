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
    { id: "maria-png", label: "装饰图片", description: "Maria 模板的蔷薇图片", kind: "gh", url: "https://example.com/gh/sample.png", success: true, status_code: 200, elapsed_ms: 123, error: null },
    { id: "npm-css", label: "npm 兼容性", description: "额外检查 normalize.css；当前内置模板没有使用它", kind: "npm", url: "https://example.com/npm/sample.css", success: true, status_code: 200, elapsed_ms: 456, error: null },
  ],
};

describe("模板 CDN 检测", () => {
  beforeEach(() => vi.resetAllMocks());

  it("检测当前输入并展示两项资源结果", async () => {
    vi.mocked(testTemplateCdn).mockResolvedValue(result);
    render(<TemplateCdnProbe baseUrl=" https://example.com/ " />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    expect(testTemplateCdn).toHaveBeenCalledWith(" https://example.com/ ");
    expect(await screen.findByText("测试链接都能访问，可以保存后试生成报告了")).toBeInTheDocument();
    expect(screen.getByText("装饰图片：可访问")).toBeInTheDocument();
    expect(screen.getByText("npm 兼容性：可访问")).toBeInTheDocument();
    expect(screen.getByText("额外检查 normalize.css；当前内置模板没有使用它")).toBeInTheDocument();
    expect(screen.getAllByText("查看检测详情")).toHaveLength(2);
  });

  it("单项失败时给出原因且不宣称可用", async () => {
    vi.mocked(testTemplateCdn).mockResolvedValue({
      ...result, usable: false,
      checks: [result.checks[0], { ...result.checks[1], success: false, status_code: 404, error: "资源请求失败：HTTP 404" }],
    });
    render(<TemplateCdnProbe baseUrl="https://example.com" />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    expect(await screen.findByText("1 / 2 个链接确认可访问，其他结果请看下方说明")).toBeInTheDocument();
    expect(screen.getByText("资源请求失败：HTTP 404")).toBeInTheDocument();
  });

  it("已有成功结果时修改地址会清空结果，且不会自动发起新检测", async () => {
    vi.mocked(testTemplateCdn).mockResolvedValue(result);
    const view = render(<TemplateCdnProbe baseUrl="https://example.com" />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    expect(await screen.findByText("测试链接都能访问，可以保存后试生成报告了")).toBeInTheDocument();
    expect(screen.getByText(result.checks[0].url)).toBeInTheDocument();
    view.rerender(<TemplateCdnProbe baseUrl="https://new.example.com" />);
    expect(screen.queryByText("测试链接都能访问，可以保存后试生成报告了")).not.toBeInTheDocument();
    expect(screen.queryByText(result.checks[0].url)).not.toBeInTheDocument();
    expect(testTemplateCdn).toHaveBeenCalledTimes(1);
  });

  it("输入改变后清除结果并忽略旧请求的迟到响应", async () => {
    let resolve!: (value: ProbeResult) => void;
    vi.mocked(testTemplateCdn).mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = render(<TemplateCdnProbe baseUrl="https://example.com" />);
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    view.rerender(<TemplateCdnProbe baseUrl="https://new.example.com" />);
    await act(async () => resolve(result));
    expect(screen.queryByText("测试链接都能访问，可以保存后试生成报告了")).not.toBeInTheDocument();
    vi.mocked(testTemplateCdn).mockRejectedValue(new Error("请求超时"));
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    await waitFor(() => expect(testTemplateCdn).toHaveBeenLastCalledWith("https://new.example.com"));
    expect(await screen.findByText("请求超时")).toBeInTheDocument();
    view.rerender(<TemplateCdnProbe baseUrl="" />);
    expect(screen.queryByText("请求超时")).not.toBeInTheDocument();
  });
});
