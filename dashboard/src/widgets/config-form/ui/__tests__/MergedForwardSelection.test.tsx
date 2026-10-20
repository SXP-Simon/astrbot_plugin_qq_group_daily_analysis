import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import configSchema from "../../../../../../_conf_schema.json";
import { apiGet, apiPost } from "../../../../shared/api/bridge";
import { useConfigViewModel } from "../../../../pages/config/model/useConfigViewModel";
import { FieldRenderer } from "../FieldRenderer";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(),
  apiGet: vi.fn(), apiPost: vi.fn(),
}));
vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

const nativeGetComputedStyle = window.getComputedStyle.bind(window);
let initialSelection: unknown = [];

function Settings() {
  const vm = useConfigViewModel();
  const field = vm.schema.basic?.items.enable_merged_forward;
  return <>
    {field && <FieldRenderer
      fieldKey="enable_merged_forward"
      fullKeyPath="basic.enable_merged_forward"
      fieldSchema={field}
      value={vm.formData.basic?.enable_merged_forward}
      error={vm.errors.basic?.enable_merged_forward}
      onChange={(next) => vm.handleFieldChange("basic", "enable_merged_forward", next)}
    />}
    <button disabled={!vm.configLoaded || vm.saving} onClick={() => void vm.handleSave()}>保存配置</button>
  </>;
}

describe("合并转发内容多选与保存", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    initialSelection = [];
    vi.spyOn(window, "getComputedStyle").mockImplementation((element) => nativeGetComputedStyle(element));
    vi.mocked(apiGet).mockImplementation(async (path) => ({ status: "ok", data: path === "config" ? {
      config: { basic: { enable_merged_forward: initialSelection, show_report_caption: false }, future: { retained: ["保留"] } },
      schema: { basic: { ...configSchema.basic, items: { enable_merged_forward: configSchema.basic.items.enable_merged_forward } } },
    } : [] }));
    vi.mocked(apiPost).mockResolvedValue({ status: "ok", message: "保存成功" });
  });
  afterEach(() => vi.restoreAllMocks());

  it("使用中文标签选择部分、全选和清空，将真实选项值保留到保存请求", async () => {
    const view = render(<Settings />);
    const selector = await screen.findByRole("combobox", { name: configSchema.basic.items.enable_merged_forward.description });
    fireEvent.mouseDown(selector);
    for (const label of ["分析报告", "词云", "漫画"]) {
      expect(screen.getByText(label, { selector: ".ant-select-item-option-content" })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByText("词云", { selector: ".ant-select-item-option-content" }));
    fireEvent.click(screen.getByText("漫画", { selector: ".ant-select-item-option-content" }));
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    await waitFor(() => expect(apiPost).toHaveBeenLastCalledWith("config", { config: {
      basic: { enable_merged_forward: ["wordcloud", "comic"], show_report_caption: false }, future: { retained: ["保留"] },
    } }));

    await waitFor(() => expect(screen.getByRole("button", { name: "保存配置" })).not.toBeDisabled());
    fireEvent.mouseDown(selector);
    fireEvent.click(screen.getByText("分析报告", { selector: ".ant-select-item-option-content" }));
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    await waitFor(() => expect(apiPost).toHaveBeenLastCalledWith("config", { config: {
      basic: { enable_merged_forward: ["wordcloud", "comic", "report"], show_report_caption: false }, future: { retained: ["保留"] },
    } }));

    await waitFor(() => expect(screen.getByRole("button", { name: "保存配置" })).not.toBeDisabled());
    const clear = view.container.querySelector(".ant-select-clear");
    expect(clear).not.toBeNull();
    fireEvent.mouseDown(clear!);
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    await waitFor(() => expect(apiPost).toHaveBeenLastCalledWith("config", { config: {
      basic: { enable_merged_forward: [], show_report_caption: false }, future: { retained: ["保留"] },
    } }));
  });

  it.each([true, false])("旧布尔值 %s 读取并原样保存其他设置时，不会意外清空已启用的内容", async (enabled) => {
    initialSelection = enabled;
    render(<Settings />);
    await screen.findByRole("combobox");
    if (enabled) {
      for (const label of ["分析报告", "词云", "漫画"]) {
        expect(screen.getByText(label, { selector: ".ant-select-selection-item-content" })).toBeInTheDocument();
      }
    } else {
      expect(screen.getByText("选择需要打包的结果，留空时全部普通发送")).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith("config", { config: {
      basic: { enable_merged_forward: enabled ? ["report", "wordcloud", "comic"] : [], show_report_caption: false },
      future: { retained: ["保留"] },
    } }));
  });
});
