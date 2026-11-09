import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { useState } from "react";
import { FieldRenderer } from "@/widgets/config-form/ui/FieldRenderer";
import { expandAnalysisPrompt } from "@/entities/config/model/promptSchemes";
import type { PromptVariable } from "@/entities/config/model/types";

const variables: Record<string, PromptVariable> = {
  messages_text: {
    label: "群聊消息",
    description: "清洗后的消息",
    example: "[20:01] [10001]: 明晚测试",
    required: true,
  },
  max_topics: {
    label: "话题上限",
    description: "当前配置值",
    example: "5",
    config_field: "max_topics",
    required: true,
  },
};

it("展开与运行时一致，支持普通 JSON、美元转义和旧的美元变量", () => {
  const result = expandAnalysisPrompt(
    '{"messages":"$messages_text","limit":${max_topics},"literal":"$${messages_text}","unknown":"${other}"}',
    variables,
    { max_topics: 8 },
  );
  expect(result.expanded).toBe(
    '{"messages":"[20:01] [10001]: 明晚测试","limit":8,"literal":"${messages_text}","unknown":"${other}"}',
  );
  expect(result.missing).toEqual([]);
  expect(result.unknown).toEqual(["other"]);
});

it("保留升级前的正文，新方案可插入变量、预览、单选，删除选中项切回原有配置", () => {
  const original = { topic_prompt: "这是升级前编辑的正文" };
  const defaultPrompt = "这是内置提示词 ${messages_text}，最多 ${max_topics} 个话题";
  function Draft() {
    const [value, setValue] = useState<unknown>(original);
    return (
      <>
        <FieldRenderer
          fieldKey="topic_analysis_prompts"
          fieldSchema={{
            type: "object",
            items: {
              topic_prompt: {
                type: "text",
                description: "话题分析",
                default: defaultPrompt,
                prompt_variables: variables,
              },
            },
          }}
          value={value}
          originalValue={original}
          onChange={setValue}
        />
        <output data-testid="draft">{JSON.stringify(value)}</output>
      </>
    );
  }
  render(<Draft />);
  expect(screen.getByRole("radio", { name: "原有配置" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "新建自定义方案" }));
  const modal = within(screen.getByRole("dialog"));
  const name = modal.getByRole("textbox", { name: "方案名称" });
  const body = modal.getByRole<HTMLTextAreaElement>("textbox", { name: "提示词正文" });
  expect(body).toHaveValue(defaultPrompt);
  fireEvent.change(body, { target: { value: "先手动编辑正文" } });
  fireEvent.click(modal.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByTestId("draft")).toHaveTextContent(JSON.stringify(original));
  expect(name).toHaveFocus();
  expect(name).toBeInvalid();
  expect(name).toHaveAccessibleDescription("请填写方案名称");
  expect(body).toBeInvalid();
  expect(body).toHaveAccessibleDescription("请插入必填变量 ${messages_text}、${max_topics}");
  fireEvent.change(name, { target: { value: "技术群" } });
  expect(name).toBeValid();
  fireEvent.click(modal.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByTestId("draft")).toHaveTextContent(JSON.stringify(original));
  expect(body).toHaveFocus();
  body.setSelectionRange(0, body.value.length);
  fireEvent.click(modal.getByRole("button", { name: "插入 ${messages_text}" }));
  expect(body).toHaveValue("${messages_text}");
  expect(body).toHaveAccessibleDescription("请插入必填变量 ${max_topics}");
  fireEvent.keyDown(body, { key: "z", ctrlKey: true });
  expect(body).toHaveValue("先手动编辑正文");
  expect(body.selectionStart).toBe(0);
  expect(body.selectionEnd).toBe(body.value.length);
  fireEvent.keyDown(body, { key: "z", ctrlKey: true });
  expect(body).toHaveValue(defaultPrompt);
  fireEvent.keyDown(body, { key: "y", ctrlKey: true });
  expect(body).toHaveValue("先手动编辑正文");
  fireEvent.keyDown(body, { key: "Z", ctrlKey: true, shiftKey: true });
  expect(body).toHaveValue("${messages_text}");
  body.setSelectionRange(body.value.length, body.value.length);
  fireEvent.click(modal.getByRole("button", { name: "插入 ${max_topics}" }));
  expect(body).toBeValid();
  fireEvent.click(modal.getByRole("button", { name: "用示例数据预览" }));
  expect(modal.getByRole("region", { name: "填入示例数据后的提示词" })).toHaveTextContent(
    "[20:01] [10001]: 明晚测试",
  );
  fireEvent.click(modal.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByRole("radio", { name: "技术群 自定义 · 待保存" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("radio", { name: "技术群 自定义 · 待保存" }));
  expect(screen.getByTestId("draft")).toHaveTextContent(
    '"topic_prompt":"${messages_text}${max_topics}"',
  );
  fireEvent.click(screen.getByRole("button", { name: "新建自定义方案" }));
  const newModal = within(screen.getByRole("dialog"));
  expect(newModal.getByRole("textbox", { name: "提示词正文" })).toHaveValue(defaultPrompt);
  fireEvent.click(newModal.getByRole("button", { name: "取消" }));
  fireEvent.click(screen.getByRole("button", { name: "删除 技术群" }));
  expect(screen.getByRole("dialog")).toHaveTextContent("此模块将切回原有配置");
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "删除" }));
  expect(screen.getByRole("radio", { name: "原有配置" })).toBeChecked();
  expect(screen.getByTestId("draft")).toHaveTextContent('"topic_prompt":"这是升级前编辑的正文"');
});
