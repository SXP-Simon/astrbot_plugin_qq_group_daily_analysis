import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FieldRenderer } from "../FieldRenderer";
import type { SchemaFieldItem } from "../../../../entities/config/model/types";
import { validateSingleFieldWithZod } from "../../../../entities/config/model/validation";

function Draft({
  fieldKey = "value",
  schema,
  initial,
}: {
  fieldKey?: string;
  schema: SchemaFieldItem;
  initial: unknown;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <FieldRenderer
        fieldKey={fieldKey}
        fieldSchema={schema}
        value={value}
        error={validateSingleFieldWithZod(fieldKey, schema, value) ?? undefined}
        onChange={setValue}
      />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

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

it("模型和人格预设可选也可手填，已有未知 ID 保留", () => {
  const change = vi.fn();
  render(
    <FieldRenderer
      fieldKey="provider_id"
      fieldSchema={{ type: "string", description: "分析模型" }}
      value="external-id"
      providers={[{ id: "model-a", name: "模型 A", type: "chat" }]}
      onChange={change}
    />,
  );
  expect(screen.getByRole("textbox", { name: "分析模型" })).toHaveValue("external-id");
  fireEvent.click(screen.getByRole("button", { name: /分析模型预设：/ }));
  fireEvent.click(screen.getByRole("option", { name: /模型 A/ }));
  expect(change).toHaveBeenCalledWith("model-a");
  fireEvent.change(screen.getByRole("textbox", { name: "分析模型" }), {
    target: { value: "manual-id" },
  });
  expect(change).toHaveBeenLastCalledWith("manual-id");
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
