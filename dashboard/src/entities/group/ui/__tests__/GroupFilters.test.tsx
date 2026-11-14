import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { GroupFilters } from "@/entities/group/ui/GroupFilters";

const groups = [
  { group_id: "123", group_name: "技术群", platform: "aiocqhttp" },
  { group_id: "123", group_name: "摄影群", platform: "telegram" },
  { group_id: "old", group_name: "old", platform: "" },
];

it("同号群使用平台和群号共同选择，并展示真实名称", () => {
  const change = vi.fn();
  render(<GroupFilters groups={groups} onPlatformChange={vi.fn()} onGroupChange={change} />);
  fireEvent.click(screen.getByRole("button", { name: "选择群聊：全部群聊" }));
  fireEvent.click(screen.getByRole("button", { name: "摄影群（123） · Telegram" }));
  expect(change).toHaveBeenCalledWith("123", "telegram");
});

it("只按群号筛选时，平台唯一才显示平台图标", () => {
  const change = vi.fn();
  const { rerender } = render(
    <GroupFilters groups={[groups[1], groups[1]]} selectedGroup="123" onGroupChange={change} />,
  );
  const trigger = screen.getByRole("button", { name: "选择群聊：123 · 全部平台" });
  expect(trigger.querySelector("img")).toHaveAttribute(
    "src",
    expect.stringContaining("telegram.svg"),
  );

  rerender(<GroupFilters groups={groups} selectedGroup="123" onGroupChange={change} />);
  expect(trigger.querySelector("img")).toBeNull();
  expect(trigger.querySelector("svg.tabler-icon-messages")).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});

it("未记录平台与全部平台分开，选定平台只展示对应群聊", () => {
  const change = vi.fn();
  render(
    <GroupFilters
      groups={groups}
      selectedPlatform=""
      onPlatformChange={change}
      onGroupChange={vi.fn()}
    />,
  );
  expect(screen.getByRole("combobox", { name: "平台" })).toHaveValue('""');
  fireEvent.change(screen.getByRole("combobox", { name: "平台" }), { target: { value: "" } });
  expect(change).toHaveBeenCalledWith(undefined);
  fireEvent.click(screen.getByRole("button", { name: "选择群聊：全部群聊" }));
  expect(screen.getByRole("button", { name: "未记录群名（old）" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /摄影群/ })).not.toBeInTheDocument();
});
