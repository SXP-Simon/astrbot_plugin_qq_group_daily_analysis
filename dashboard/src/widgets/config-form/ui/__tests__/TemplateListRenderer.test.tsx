import { useState } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { SchemaFieldItem } from "@/entities/config/model/types";
import { TemplateListRenderer } from "@/widgets/config-form/ui/TemplateListRenderer";
import { useTemplateListModel } from "@/widgets/config-form/model/useTemplateListModel";

vi.mock("@/widgets/config-form/ui/FieldRenderer", () => ({
  FieldRenderer: ({
    fieldKey,
    value,
    onChange,
  }: {
    fieldKey: string;
    value: unknown;
    onChange: (value: unknown) => void;
  }) => (
    <label>
      {fieldKey}
      <input value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />
    </label>
  ),
}));
vi.mock("@/features/test-t2i/ui/T2iProbe", () => ({ T2iProbe: () => null }));
vi.mock("@/features/manage-typst-fonts/ui/TypstFonts", () => ({
  TypstFonts: () => null,
}));
vi.mock("@/features/manage-template-resources/ui/TemplateResources", () => ({
  TemplateResources: () => null,
}));

const schema: SchemaFieldItem = {
  type: "template_list",
  templates: {
    first: {
      name: "第一类",
      items: {
        name: { type: "string", default: "第一类" },
        mode: { type: "string", default: "local" },
        local: { type: "string", default: "本地设置", condition: { mode: "local" } },
        secret: { type: "string", invisible: true },
        options: { type: "object", default: { values: ["示例"] } },
      },
    },
    second: { name: "第二类", items: { name: { type: "string", default: "第二类" } } },
  },
};
const initial = [
  { __template_key: "first", name: "主方案", priority: 10, extra: { retain: true } },
  { __template_key: "second", name: "备用方案", priority: 20 },
];
function Editor() {
  const [value, onChange] = useState<unknown>(initial);
  return (
    <>
      <TemplateListRenderer
        fieldKey="plans"
        fieldSchema={schema}
        value={value}
        onChange={onChange}
      />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

it("新增保留预设默认值并复制嵌套数据，编辑和排序保留未知字段及优先级", () => {
  const change = vi.fn();
  const vm = useTemplateListModel(schema, initial, change);
  vm.add("first");
  const first = change.mock.calls[0][0];
  vm.add("first");
  const second = change.mock.calls[1][0];
  expect(first).toMatchObject([
    ...initial,
    { __template_key: "first", name: "第一类", mode: "local", options: { values: ["示例"] } },
  ]);
  expect(first[2].options).not.toBe(second[2].options);
  vm.change(0, { name: "新名称" });
  expect(change).toHaveBeenLastCalledWith([{ ...initial[0], name: "新名称" }, initial[1]]);
  vm.move(0, 1);
  expect(change).toHaveBeenLastCalledWith([initial[1], initial[0]]);
  vm.move(0, -1);
  expect(change).toHaveBeenCalledTimes(4);
  expect(initial[0].name).toBe("主方案");
});

it("缺省字段按默认条件显示，按钮具备名称且可新增、编辑和排序", async () => {
  render(<Editor />);
  expect(screen.getByLabelText("local")).toHaveValue("本地设置");
  expect(screen.queryByLabelText("secret")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "上移 主方案" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "下移 备用方案" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "下移 主方案" }));
  expect(screen.getByRole("region", { name: "1. 备用方案" })).toBeInTheDocument();
  fireEvent.change(
    within(screen.getByRole("region", { name: "2. 主方案" })).getByLabelText("name"),
    { target: { value: "改名主方案" } },
  );
  expect(screen.getByTestId("value")).toHaveTextContent('"retain":true');
  const add = screen.getByRole("button", { name: "添加配置项" });
  add.focus();
  fireEvent.click(add);
  const dialog = screen.getByRole("dialog", { name: "添加配置项" });
  fireEvent.click(within(dialog).getByRole("button", { name: "第二类" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByRole("region", { name: "3. 第二类" })).toBeInTheDocument();
  await waitFor(() => expect(add).toHaveFocus());
});

it("删除需确认，取消保留条目并恢复焦点，确认后聚焦添加入口", async () => {
  render(<Editor />);
  const remove = screen.getByRole("button", { name: "删除 主方案" });
  remove.focus();
  fireEvent.click(remove);
  let dialog = screen.getByRole("dialog", { name: "删除配置条目？" });
  expect(dialog).toHaveTextContent("主方案");
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "取消" })).toHaveFocus());
  fireEvent.click(within(dialog).getByRole("button", { name: "取消" }));
  await waitFor(() => expect(remove).toHaveFocus());
  fireEvent.click(remove);
  dialog = screen.getByRole("dialog", { name: "删除配置条目？" });
  fireEvent.click(within(dialog).getByRole("button", { name: "确认删除" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByTestId("value")).not.toHaveTextContent("主方案");
  await waitFor(() => expect(screen.getByRole("button", { name: "添加配置项" })).toHaveFocus());
});

it("确认期间配置被替换时拒绝删除错位条目，非法列表不被静默覆盖", () => {
  const onChange = vi.fn();
  const view = render(
    <TemplateListRenderer
      fieldKey="plans"
      fieldSchema={schema}
      value={initial}
      onChange={onChange}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "删除 主方案" }));
  view.rerender(
    <TemplateListRenderer
      fieldKey="plans"
      fieldSchema={schema}
      value={[initial[1], initial[0]]}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("条目已变更");
  expect(screen.getByRole("button", { name: "确认删除" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  view.rerender(
    <TemplateListRenderer
      fieldKey="plans"
      fieldSchema={schema}
      value={[null]}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("格式不正确");
  expect(screen.getByRole("button", { name: "添加配置项" })).toBeDisabled();
  expect(onChange).not.toHaveBeenCalled();
});
