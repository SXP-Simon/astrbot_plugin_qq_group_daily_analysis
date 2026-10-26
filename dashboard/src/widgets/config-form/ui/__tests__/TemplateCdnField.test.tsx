import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { testTemplateCdn } from "../../../../entities/config/api/configApi";
import { DEFAULT_TEMPLATE_CDN_BASE_URL, TEMPLATE_CDN_PRESETS } from "../../../../entities/config/model/renderingConfig";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../entities/config/api/configApi", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../entities/config/api/configApi")>(),
  testTemplateCdn: vi.fn(),
}));
vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

function CdnField({ initial, fieldKey = "cdn_base_url" }: { initial: string; fieldKey?: string }) {
  const [value, setValue] = useState<unknown>(initial);
  return (
    <FieldRenderer
      fieldKey={fieldKey}
      fieldSchema={{ type: "string", description: "模板资源 CDN 基础地址", default: DEFAULT_TEMPLATE_CDN_BASE_URL }}
      value={value}
      onChange={setValue}
    />
  );
}

describe("CDN 预设与自定义地址", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(testTemplateCdn).mockResolvedValue({ base_url: "https://fastly.jsdelivr.net", usable: true, checks: [] });
  });

  it("保留已有自定义地址，展开时提供国内和海外候选", () => {
    render(<CdnField initial="https://custom.example/" />);
    const input = screen.getByRole("combobox");
    expect(input).toHaveValue("https://custom.example/");
    fireEvent.mouseDown(input);
    fireEvent.focus(input);
    for (const option of TEMPLATE_CDN_PRESETS) {
      expect(screen.getAllByText(option.label).length).toBeGreaterThan(0);
    }
    expect(testTemplateCdn).not.toHaveBeenCalled();
  });

  it("选择预设后按当前地址检测，仍可改填自定义地址", async () => {
    render(<CdnField initial={DEFAULT_TEMPLATE_CDN_BASE_URL} />);
    const input = screen.getByRole("combobox");
    fireEvent.mouseDown(input);
    fireEvent.focus(input);
    fireEvent.click(screen.getByText("海外备选 · Fastly · https://fastly.jsdelivr.net"));
    expect(input).toHaveValue("https://fastly.jsdelivr.net");
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    await waitFor(() => expect(testTemplateCdn).toHaveBeenCalledWith("https://fastly.jsdelivr.net"));
    fireEvent.change(input, { target: { value: "https://my-cdn.example/" } });
    expect(input).toHaveValue("https://my-cdn.example/");
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    await waitFor(() => expect(testTemplateCdn).toHaveBeenLastCalledWith("https://my-cdn.example/"));
  });

  it("允许清空地址，继续使用原有的默认地址规则", async () => {
    render(<CdnField initial={DEFAULT_TEMPLATE_CDN_BASE_URL} />);
    fireEvent.click(screen.getByLabelText("close-circle"));
    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "检测可用性" })).not.toBeInTheDocument();
    expect(testTemplateCdn).not.toHaveBeenCalled();
  });

  it.each(["cdn_base_url"])("环境字段 %s 保留预设和地址检测", async (key) => {
    render(<CdnField initial="https://custom.example" fieldKey={key} />);
    expect(screen.getByRole("combobox")).toHaveValue("https://custom.example");
    fireEvent.click(screen.getByRole("button", { name: "检测可用性" }));
    await waitFor(() => expect(testTemplateCdn).toHaveBeenCalledWith("https://custom.example"));
  });

  it("环境地址留空时不误测默认站点", () => {
    render(<CdnField initial="" fieldKey="cdn_base_url" />);
    expect(screen.queryByRole("button", { name: "检测可用性" })).not.toBeInTheDocument();
    expect(screen.getByText(/留空使用当前资源环境的预设/)).toBeInTheDocument();
    expect(testTemplateCdn).not.toHaveBeenCalled();
  });
});
