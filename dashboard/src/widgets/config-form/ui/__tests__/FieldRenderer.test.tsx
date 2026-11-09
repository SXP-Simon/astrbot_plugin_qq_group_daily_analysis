import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FieldRenderer } from "@/widgets/config-form/ui/FieldRenderer";
import type { SchemaFieldItem } from "@/entities/config/model/types";
import { validateSingleFieldWithZod } from "@/entities/config/model/validation";

function Draft({
  fieldKey = "value",
  schema,
  initial,
  trackChanges = false,
}: {
  fieldKey?: string;
  schema: SchemaFieldItem;
  initial: unknown;
  trackChanges?: boolean;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <FieldRenderer
        fieldKey={fieldKey}
        fieldSchema={schema}
        value={value}
        originalValue={initial}
        modified={trackChanges ? JSON.stringify(value) !== JSON.stringify(initial) : undefined}
        error={validateSingleFieldWithZod(fieldKey, schema, value) ?? undefined}
        onChange={setValue}
      />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

it("只标记实际修改的方案字段，换序保持比较基准，撤销后恢复", () => {
  const original = [
    { __template_key: "plan", name: "主方案", priority: 10, quality: 80 },
    { __template_key: "plan", name: "备用方案", priority: 20, quality: 80 },
  ];
  render(
    <Draft
      fieldKey="plans"
      trackChanges
      initial={original}
      schema={{
        type: "template_list",
        description: "方案列表",
        templates: {
          plan: {
            name: "方案",
            items: {
              name: { type: "string", description: "名称" },
              priority: { type: "int", description: "优先级" },
              quality: { type: "int", description: "图片质量" },
            },
          },
        },
      }}
    />,
  );
  expect(screen.queryByText("已修改")).not.toBeInTheDocument();
  fireEvent.change(screen.getAllByRole("spinbutton", { name: "优先级" })[0], {
    target: { value: "12" },
  });
  expect(
    screen.getAllByRole("spinbutton", { name: "优先级" })[0].closest("section"),
  ).toHaveAttribute("data-modified", "true");
  expect(
    screen.getAllByRole("spinbutton", { name: "图片质量" })[0].closest("section"),
  ).not.toHaveAttribute("data-modified");
  fireEvent.click(screen.getByRole("button", { name: "下移 主方案" }));
  const priorities = screen.getAllByRole("spinbutton", { name: "优先级" });
  expect(priorities[0]).toHaveValue(20);
  expect(priorities[0].closest("section")).not.toHaveAttribute("data-modified");
  expect(priorities[1]).toHaveValue(12);
  expect(priorities[1].closest("section")).toHaveAttribute("data-modified", "true");
  fireEvent.change(priorities[1], { target: { value: "10" } });
  expect(priorities[1].closest("section")).not.toHaveAttribute("data-modified");
  fireEvent.click(screen.getByRole("button", { name: "上移 主方案" }));
  expect(screen.queryByText("已修改")).not.toBeInTheDocument();
});

it("已修改和错误状态分别表达，错误字段保留红色提示", () => {
  render(<Draft trackChanges initial={1} schema={{ type: "int", description: "并发", min: 1 }} />);
  fireEvent.change(screen.getByRole("spinbutton", { name: "并发" }), { target: { value: "0" } });
  expect(screen.getByText("已修改")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("不能小于 1");
  expect(screen.getByRole("spinbutton").closest("section")).toHaveClass("bg-destructive/5");
});

it("布尔和数字控件保留原始类型，恢复默认深拷贝配置值", () => {
  const view = render(
    <Draft schema={{ type: "bool", description: "启用分析", default: true }} initial={false} />,
  );
  fireEvent.click(screen.getByRole("switch", { name: "启用分析" }));
  expect(screen.getByTestId("value")).toHaveTextContent("true");
  view.unmount();
  render(<Draft schema={{ type: "float", description: "透明度", default: 0.12 }} initial={0.1} />);
  fireEvent.change(screen.getByRole("spinbutton", { name: "透明度" }), {
    target: { value: "0.25" },
  });
  expect(screen.getByTestId("value")).toHaveTextContent("0.25");
  fireEvent.click(screen.getByRole("button", { name: "恢复默认" }));
  expect(screen.getByTestId("value")).toHaveTextContent("0.12");
});

it("多选输出保留用户选择的发送顺序，自由列表去空白和重复", () => {
  const view = render(
    <Draft
      fieldKey="output_format"
      schema={{ type: "list", description: "输出格式", options: ["image", "text", "html"] }}
      initial={["html"]}
    />,
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "图片报告 (image)" }));
  expect(screen.getByTestId("value")).toHaveTextContent('["html","image"]');
  fireEvent.click(screen.getByRole("checkbox", { name: "HTML 网页报告 (html)" }));
  expect(screen.getByTestId("value")).toHaveTextContent('["image"]');
  view.unmount();
  render(<Draft schema={{ type: "list", description: "名单" }} initial={["member-a"]} />);
  const input = screen.getByRole("textbox", { name: "添加名单" });
  fireEvent.change(input, { target: { value: " member-b " } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(screen.getByTestId("value")).toHaveTextContent('["member-a","member-b"]');
  fireEvent.change(input, { target: { value: "member-b" } });
  fireEvent.click(screen.getByRole("button", { name: "添加条目" }));
  expect(screen.getByTestId("value")).toHaveTextContent('["member-a","member-b"]');
  fireEvent.click(screen.getByRole("button", { name: "移除 member-a" }));
  expect(screen.getByTestId("value")).toHaveTextContent('["member-b"]');
});

it("嵌套编辑保留未知字段和多行提示词，隐藏字段不出现", () => {
  render(
    <Draft
      schema={{
        type: "object",
        items: {
          prompt: { type: "text", description: "提示词" },
          hidden: { type: "string", description: "隐藏字段", invisible: true },
        },
      }}
      initial={{ prompt: "旧正文", unknown: { keep: true }, hidden: "secret" }}
    />,
  );
  expect(screen.queryByLabelText("隐藏字段")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "提示词" }), {
    target: { value: "第一行\n第二行" },
  });
  expect(JSON.parse(screen.getByTestId("value").textContent || "{}")).toEqual({
    prompt: "第一行\n第二行",
    unknown: { keep: true },
    hidden: "secret",
  });
});

it("JSON 编辑的不完整内容不会丢失，修正后恢复对象且清除错误", () => {
  render(<Draft schema={{ type: "object", description: "扩展数据" }} initial={{ ready: true }} />);
  const input = screen.getByRole("textbox", { name: "扩展数据" });
  fireEvent.change(input, { target: { value: '{"ready":' } });
  expect(input).toHaveValue('{"ready":');
  expect(screen.getByRole("alert")).toHaveTextContent("JSON 对象");
  fireEvent.change(input, { target: { value: '{"ready":false}' } });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByTestId("value")).toHaveTextContent('{"ready":false}');
});

it.each(["模型", "人格"])("%s只能选择已有项，搜索不写入配置，默认和清空仍可用", (kind) => {
  const change = vi.fn();
  const title = `分析${kind}`;
  render(
    <FieldRenderer
      fieldKey={kind === "模型" ? "provider_id" : "persona_id"}
      fieldSchema={{ type: "string", description: title, hint: "可选择默认配置" }}
      value="external-id"
      providers={[{ id: "model-a", name: "模型 A", type: "chat" }]}
      personas={[{ id: "persona-a", name: "人格 A" }]}
      onChange={change}
    />,
  );
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  const trigger = screen.getByRole("button", { name: `${title}：external-id` });
  expect(trigger).toHaveAccessibleDescription("可选择默认配置");
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(trigger);
  const search = screen.getByRole("combobox", { name: `搜索${title}` });
  fireEvent.change(search, {
    target: { value: "manual-id" },
  });
  fireEvent.keyDown(search, { key: "Enter" });
  expect(screen.getByText("没有匹配的选项")).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  fireEvent.change(search, { target: { value: `${kind} A` } });
  fireEvent.click(screen.getByRole("option", { name: new RegExp(`${kind} A`) }));
  expect(change).toHaveBeenCalledWith(kind === "模型" ? "model-a" : "persona-a");
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("option", { name: `使用默认${kind}` }));
  expect(change).toHaveBeenLastCalledWith("");
  fireEvent.click(screen.getByRole("button", { name: `清空 ${title}` }));
  expect(change).toHaveBeenLastCalledWith("");
});

it("候选未加载或刷新后移除当前项时，保留已有 ID 和字段错误关联", () => {
  const change = vi.fn();
  const field = {
    fieldKey: "custom_model",
    fieldSchema: {
      type: "string",
      description: "专用模型",
      _special: "select_provider",
    },
    value: "saved-id",
    error: "请选择可用的模型",
    onChange: change,
  };
  const view = render(<FieldRenderer {...field} />);
  expect(screen.getByRole("button", { name: "专用模型：saved-id" })).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(screen.getByRole("button", { name: "专用模型：saved-id" })).toHaveAccessibleDescription(
    "请选择可用的模型",
  );
  view.rerender(<FieldRenderer {...field} providers={[{ id: "saved-id", name: "已配置模型" }]} />);
  expect(screen.getByRole("button", { name: /专用模型：已配置模型/ })).toBeInTheDocument();
  view.rerender(<FieldRenderer {...field} providers={[]} />);
  expect(screen.getByRole("button", { name: "专用模型：saved-id" })).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});

it("资源地址仍可填写自定义值，也能从预设选择", () => {
  const change = vi.fn();
  render(
    <FieldRenderer
      fieldKey="google_fonts"
      fieldSchema={{
        type: "string",
        description: "字体 CSS 地址",
        options: ["https://fonts.example"],
      }}
      value=""
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByRole("textbox", { name: "字体 CSS 地址" }), {
    target: { value: "https://custom.example" },
  });
  expect(change).toHaveBeenLastCalledWith("https://custom.example");
  fireEvent.click(screen.getByRole("button", { name: /字体 CSS 地址预设：/ }));
  fireEvent.click(screen.getByRole("option", { name: "https://fonts.example" }));
  expect(change).toHaveBeenLastCalledWith("https://fonts.example");
});

it("Token 默认隐藏，可明确切换显示，修改继续传递原值", () => {
  const change = vi.fn();
  render(
    <FieldRenderer
      fieldKey="service_token"
      fieldSchema={{ type: "string", description: "服务 Token" }}
      value="secret"
      onChange={change}
    />,
  );
  expect(screen.getByLabelText("服务 Token")).toHaveAttribute("type", "password");
  fireEvent.click(screen.getByRole("button", { name: "显示 Token" }));
  expect(screen.getByRole("textbox", { name: "服务 Token" })).toHaveValue("secret");
  fireEvent.change(screen.getByLabelText("服务 Token"), { target: { value: "new-secret" } });
  expect(change).toHaveBeenCalledWith("new-secret");
});
