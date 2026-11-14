import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { SearchSelect } from "@/shared/ui/search-select";

it("带图标的选项仍按原名称搜索和键盘选择，关闭后更新触发器", () => {
  function Selector() {
    const [value, setValue] = useState("");
    return (
      <SearchSelect
        label="模型"
        value={value}
        onChange={setValue}
        virtual
        options={[
          { value: "", label: "默认模型" },
          { value: "qwen", label: "Qwen Chat" },
          { value: "deepseek", label: "DeepSeek Chat", icon: <svg data-testid="model-icon" /> },
        ]}
      />
    );
  }
  render(<Selector />);
  fireEvent.click(screen.getByRole("button", { name: "模型：默认模型" }));
  const dialog = screen.getByRole("dialog");
  const search = within(dialog).getByRole("combobox");
  fireEvent.change(search, { target: { value: "Chat" } });
  const first = within(dialog).getByRole("option", { name: "Qwen Chat" });
  const second = within(dialog).getByRole("option", { name: "DeepSeek Chat" });
  expect(first).toBeVisible();
  expect(second).toBeVisible();
  fireEvent.keyDown(search, { key: "ArrowDown" });
  expect(search).toHaveAttribute("aria-activedescendant", first.id);
  fireEvent.keyDown(search, { key: "ArrowDown" });
  expect(search).toHaveAttribute("aria-activedescendant", second.id);
  fireEvent.keyDown(search, { key: "Enter" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const trigger = screen.getByRole("button", { name: "模型：DeepSeek Chat" });
  expect(within(trigger).getByTestId("model-icon")).toBeVisible();
});
