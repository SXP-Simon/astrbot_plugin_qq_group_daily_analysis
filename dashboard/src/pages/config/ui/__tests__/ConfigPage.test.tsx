import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { SchemaFieldItem } from "../../../../entities/config/model/types";
import {
  fetchPluginConfig,
  savePluginConfig,
  fetchAvailableProviders,
  fetchAvailablePersonas,
} from "../../../../entities/config/api/configApi";
import { ConfigPage } from "../ConfigPage";
import { useConfigViewModel } from "../../model/useConfigViewModel";

vi.mock("../../../../entities/config/api/configApi", () => ({
  fetchPluginConfig: vi.fn(),
  savePluginConfig: vi.fn(),
  fetchAvailableProviders: vi.fn(),
  fetchAvailablePersonas: vi.fn(),
}));
vi.mock("../../../../widgets/config-form/ui/FieldRenderer", () => ({
  FieldRenderer: ({
    fieldKey,
    fieldSchema,
    value,
    onChange,
  }: {
    fieldKey: string;
    fieldSchema: SchemaFieldItem;
    value: unknown;
    onChange: (value: unknown) => void;
  }) => (
    <label>
      {fieldSchema.description}
      <input
        aria-label={fieldSchema.description}
        data-field={fieldKey}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  ),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }));

const config = {
  basic: { title: "原报告名", hidden: "不显示", unknown: "保留扩展字段" },
  advanced: { endpoint: "https://example.com", note: "保留说明" },
};
const schema = {
  basic: {
    type: "object" as const,
    description: "基础设置",
    items: {
      title: { type: "string", description: "报告名称" },
      hidden: { type: "string", description: "隐藏项", invisible: true },
    },
  },
  advanced: {
    type: "object" as const,
    description: "高级渲染",
    hint: "调整访问地址",
    items: {
      endpoint: { type: "string", description: "服务地址" },
      note: { type: "string", description: "备注" },
    },
  },
};
function Page() {
  return <ConfigPage viewModel={useConfigViewModel()} />;
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchPluginConfig).mockResolvedValue({ config, schema });
  vi.mocked(fetchAvailableProviders).mockResolvedValue([]);
  vi.mocked(fetchAvailablePersonas).mockResolvedValue([]);
});

it("保留分组与编辑值，保存失败直接说明原因，成功保存保留未知字段", async () => {
  vi.mocked(savePluginConfig)
    .mockResolvedValueOnce({ success: false, message: "配置版本冲突" })
    .mockResolvedValueOnce({ success: true });
  render(<Page />);
  const field = await screen.findByRole("textbox", { name: "报告名称" });
  fireEvent.change(field, { target: { value: "新报告名" } });
  const nav = screen.getByRole("navigation", { name: "配置分组" });
  fireEvent.click(within(nav).getByRole("button", { name: /高级渲染/ }));
  expect(screen.getByRole("textbox", { name: "服务地址" })).toHaveValue("https://example.com");
  fireEvent.click(within(nav).getByRole("button", { name: /基础设置/ }));
  expect(screen.getByRole("textbox", { name: "报告名称" })).toHaveValue("新报告名");
  expect(screen.queryByText("隐藏项")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("配置版本冲突");
  expect(screen.getByRole("textbox", { name: "报告名称" })).toHaveValue("新报告名");
  fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "保存配置" })).toBeDisabled());
  expect(savePluginConfig).toHaveBeenLastCalledWith({
    ...config,
    basic: { ...config.basic, title: "新报告名" },
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("重新读取前确认丢弃草稿，取消保留编辑并返回按钮焦点", async () => {
  render(<Page />);
  fireEvent.change(await screen.findByRole("textbox", { name: "报告名称" }), {
    target: { value: "草稿" },
  });
  const reload = screen.getByRole("button", { name: "重新读取" });
  reload.focus();
  fireEvent.click(reload);
  expect(screen.getByRole("dialog", { name: "放弃未保存的修改？" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "继续编辑" }));
  await waitFor(() => expect(reload).toHaveFocus());
  expect(fetchPluginConfig).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("textbox", { name: "报告名称" })).toHaveValue("草稿");
  fireEvent.click(reload);
  fireEvent.click(screen.getByRole("button", { name: "放弃修改并重新读取" }));
  await waitFor(() =>
    expect(screen.getByRole("textbox", { name: "报告名称" })).toHaveValue("原报告名"),
  );
  expect(fetchPluginConfig).toHaveBeenCalledTimes(2);
});

it("搜索键名、分组名称和说明能找到对应字段，清空后回到原分组", async () => {
  render(<Page />);
  await screen.findByRole("textbox", { name: "报告名称" });
  const search = screen.getByRole("searchbox", { name: "搜索配置名称或说明" });
  fireEvent.change(search, { target: { value: "endpoint" } });
  expect(screen.getByRole("textbox", { name: "服务地址" })).toBeVisible();
  expect(screen.queryByRole("textbox", { name: "备注" })).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("navigation", { name: "配置分组" })).getByRole("button", {
      name: "高级渲染 1 项",
    }),
  ).toHaveAttribute("aria-current", "page");
  for (const keyword of ["高级渲染", "调整访问地址"]) {
    fireEvent.change(search, { target: { value: keyword } });
    expect(screen.getByRole("textbox", { name: "服务地址" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "备注" })).toBeVisible();
  }
  fireEvent.change(search, { target: { value: "没有这个字段" } });
  expect(screen.getByText("未找到匹配该关键词的配置项")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "清除配置搜索" }));
  expect(screen.getByRole("textbox", { name: "报告名称" })).toHaveValue("原报告名");
  fireEvent.change(screen.getByLabelText("配置分组", { selector: "select" }), {
    target: { value: "advanced" },
  });
  expect(screen.getByRole("textbox", { name: "服务地址" })).toBeVisible();
});

it("重新读取失败保留草稿但禁用编辑和保存，重试读取后恢复", async () => {
  render(<Page />);
  fireEvent.change(await screen.findByRole("textbox", { name: "报告名称" }), {
    target: { value: "草稿" },
  });
  vi.mocked(fetchPluginConfig).mockRejectedValueOnce(new Error("读取超时"));
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  fireEvent.click(screen.getByRole("button", { name: "放弃修改并重新读取" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("读取超时");
  const field = screen.getByRole("textbox", { name: "报告名称" });
  expect(field).toHaveValue("草稿");
  expect(field).toBeDisabled();
  expect(screen.getByRole("button", { name: "保存配置" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "放弃修改并重新读取" })),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(field).toBeEnabled();
});
