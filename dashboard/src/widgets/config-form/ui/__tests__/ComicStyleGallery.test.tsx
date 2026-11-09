import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import schema from "@plugin-config";
import {
  validateFieldIssues,
  validateSingleFieldWithZod,
} from "@/entities/config/model/validation";
import type { SchemaFieldItem } from "@/entities/config/model/types";
import { FieldRenderer } from "@/widgets/config-form/ui/FieldRenderer";
import { comicPresets } from "@/entities/comic/model/comicPresets";
import { ComicStyleGallery } from "@/widgets/config-form/ui/ComicStyleGallery";

const field: SchemaFieldItem = schema.daily_comic.items.comic_styles;

function Settings({
  saved = field.default,
  onChange,
}: {
  saved?: unknown;
  onChange?: (value: unknown) => void;
}) {
  const [value, setValue] = useState<unknown>(saved);
  return (
    <FieldRenderer
      fieldKey="comic_styles"
      fieldSchema={field}
      originalValue={saved}
      value={value}
      subErrors={validateFieldIssues("comic_styles", field, value)}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

it("用风格方案选用内置模板，恢复默认时只清空当前提示词覆盖", () => {
  render(<Settings />);
  fireEvent.click(screen.getByRole("button", { name: "浏览漫画风格" }));
  const dialog = screen.getByRole("dialog", { name: "漫画风格" });
  const preset = comicPresets.find(({ id }) => id === "pixel_rpg")!;
  fireEvent.click(within(dialog).getByRole("button", { name: `选用 ${preset.name}` }));
  const row = screen.getByRole("region", { name: `1. ${preset.name}` });
  const prompt = within(row).getByRole("textbox", { name: "自定义分镜提示词" });
  fireEvent.click(within(row).getByRole("button", { name: "变量与预览" }));
  const editor = within(screen.getByRole("dialog", { name: "漫画分镜提示词" }));
  expect(editor.getByRole("textbox", { name: "分镜提示词正文" })).toHaveValue(preset.prompt);
  expect(editor.getByRole("button", { name: "应用到草稿" })).toBeDisabled();
  fireEvent.click(editor.getByRole("button", { name: "用示例数据预览" }));
  expect(editor.getByRole("region", { name: "填入示例数据后的提示词" })).toHaveTextContent(
    "1. 话题: 群友筹划露营",
  );
  fireEvent.click(editor.getByRole("button", { name: "取消" }));
  expect(prompt).toHaveValue("");
  fireEvent.click(within(row).getByRole("button", { name: "复制内置提示词并编辑" }));
  expect(prompt).toHaveValue(preset.prompt);
  fireEvent.change(prompt, { target: { value: "自定义分镜" } });
  const promptField = prompt.closest<HTMLElement>('[data-field-key="prompt_override"]');
  if (!promptField) throw new Error("找不到当前风格的提示词字段");
  fireEvent.click(within(promptField).getByRole("button", { name: "恢复默认" }));
  expect(prompt).toHaveValue("");
  expect(screen.getByRole("region", { name: `1. ${preset.name}` })).toBeInTheDocument();
});

it("旧分镜插入变量可撤销，缺少必填变量时不能应用", () => {
  render(
    <Settings
      saved={[
        { preset_id: "classic", prompt_override: '输出 {"scene":"分镜"}，共 {max_count} 格。' },
      ]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "变量与预览" }));
  const editor = within(screen.getByRole("dialog", { name: "漫画分镜提示词" }));
  const body = editor.getByRole<HTMLTextAreaElement>("textbox", { name: "分镜提示词正文" });
  body.setSelectionRange(body.value.length, body.value.length);
  fireEvent.click(editor.getByRole("button", { name: "插入 {chat_content}" }));
  expect(body.value).toMatch(/\{chat_content\}$/);
  fireEvent.keyDown(body, { key: "z", ctrlKey: true });
  expect(body.value).not.toContain("{chat_content}");
  fireEvent.click(editor.getByRole("button", { name: "用示例数据预览" }));
  const preview = editor.getByRole("region", { name: "填入示例数据后的提示词" });
  expect(preview).toHaveTextContent('输出 {"scene":"分镜"}，共 2 格。');
  expect(preview).not.toHaveTextContent("群友筹划露营");
  fireEvent.change(body, { target: { value: "旧分镜：{chat_content}" } });
  fireEvent.click(editor.getByRole("button", { name: "应用到草稿" }));
  expect(body).toHaveFocus();
  expect(body).toHaveAccessibleDescription("请插入必填变量 ${topic_count}");
  body.setSelectionRange(body.value.length, body.value.length);
  fireEvent.click(editor.getByRole("button", { name: "插入 {topic_count}" }));
  expect(body).toBeValid();
  expect(preview).toHaveTextContent("旧分镜：1. 话题: 群友筹划露营");
  fireEvent.click(editor.getByRole("button", { name: "应用到草稿" }));
  expect(screen.getByRole("textbox", { name: "自定义分镜提示词" })).toHaveValue(
    "旧分镜：{chat_content}{topic_count}",
  );
});

it("使用所选模板 CDN，图片加载失败后显示缺图提示", () => {
  const onSelect = () => {};
  const { rerender } = render(
    <ComicStyleGallery cdnBaseUrl="https://cdn.example" onSelect={onSelect} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "浏览漫画风格" }));
  const button = screen.getByRole("button", { name: "预览 原版漫画" });
  const image = within(button).getByRole("img");
  expect(image).toHaveAttribute(
    "src",
    "https://cdn.example/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/comic_previews/classic/thumbnail.webp",
  );
  fireEvent.error(image);
  expect(within(button).getByText("暂无预览图")).toBeVisible();
  expect(within(button).queryByRole("img")).not.toBeInTheDocument();

  rerender(<ComicStyleGallery cdnBaseUrl={null} onSelect={onSelect} />);
  expect(screen.getByRole("alert")).toHaveTextContent("CDN 地址无效");
});

it("新增独立自定义风格后，保存前要求名称和正文", () => {
  let draft: unknown;
  render(<Settings onChange={(value) => (draft = value)} />);
  fireEvent.click(screen.getByRole("button", { name: "添加风格方案" }));
  const row = within(screen.getByRole("region", { name: "2. 原版漫画" }));
  expect(row.getByRole("textbox", { name: "方案名称" })).toHaveAccessibleDescription(
    "方案名称「原版漫画」已使用，请更换名称。",
  );
  fireEvent.change(row.getByRole("combobox", { name: "风格来源" }), {
    target: { value: "custom" },
  });
  const custom = within(screen.getByRole("region", { name: "2. 自定义风格" }));
  expect(custom.queryByRole("button", { name: "浏览漫画风格" })).not.toBeInTheDocument();
  const name = custom.getByRole("textbox", { name: "方案名称" });
  const prompt = custom.getByRole("textbox", { name: "自定义分镜提示词" });
  expect(name).toBeInvalid();
  expect(name).toHaveAccessibleDescription("请填写方案名称");
  expect(prompt).toBeInvalid();
  expect(prompt).toHaveAccessibleDescription("请填写分镜提示词");
  expect(
    within(screen.getByRole("region", { name: "1. 原版漫画" })).queryByRole("alert"),
  ).toBeNull();
  fireEvent.change(name, {
    target: { value: "四格手绘" },
  });
  expect(name).toBeValid();
  expect(prompt).toBeInvalid();
  fireEvent.change(prompt, {
    target: { value: "用 ${topic_count} 格手绘记录话题：${chat_content}" },
  });
  expect(validateSingleFieldWithZod("comic_styles", field, draft)).toBeNull();
  expect(draft).toEqual([
    expect.objectContaining({ preset_id: "classic" }),
    expect.objectContaining({
      preset_id: "custom",
      name: "四格手绘",
      prompt_override: "用 ${topic_count} 格手绘记录话题：${chat_content}",
    }),
  ]);
});

it("从重新读取的配置中按名称复用风格，并保留新建入口", () => {
  const preset = {
    __template_key: "style",
    preset_id: "custom",
    name: "四格手绘",
    prompt_override: "用 ${topic_count} 格手绘记录话题：${chat_content}",
    enable: false,
  };
  let draft: unknown;
  render(<Settings saved={[preset]} onChange={(value) => (draft = value)} />);

  const original = within(screen.getByRole("region", { name: "1. 四格手绘" }));
  expect(original.getByRole("combobox", { name: "风格来源" })).toHaveDisplayValue(
    "四格手绘（自定义）",
  );
  const remove = original.getByRole("button", { name: "删除 四格手绘" });
  fireEvent.click(remove);
  const dialog = within(screen.getByRole("dialog", { name: "删除配置条目？" }));
  expect(dialog.getByText(/此自定义风格会从下拉框消失/)).toBeVisible();
  expect(dialog.getByText(/关闭「启用此方案」/)).toBeVisible();
  fireEvent.click(dialog.getByRole("button", { name: "取消" }));
  fireEvent.click(screen.getByRole("button", { name: "添加风格方案" }));
  const added = within(screen.getByRole("region", { name: "2. 原版漫画" }));
  const source = added.getByRole("combobox", { name: "风格来源" });
  const savedOption = within(source).getByRole("option", { name: "四格手绘（自定义）" });
  expect(within(source).getByRole("option", { name: "自定义风格" })).toBeInTheDocument();
  fireEvent.change(source, { target: { value: savedOption.getAttribute("value") } });
  expect(screen.getByRole("region", { name: "2. 四格手绘（2）" })).toBeInTheDocument();
  expect(draft).toEqual([preset, { ...preset, name: "四格手绘（2）", enable: true }]);
  expect(validateSingleFieldWithZod("comic_styles", field, draft)).toBeNull();

  fireEvent.click(remove);
  const deleteOriginalDialog = within(screen.getByRole("dialog", { name: "删除配置条目？" }));
  expect(deleteOriginalDialog.getByText(/此自定义风格会从下拉框消失/)).toBeVisible();
});
