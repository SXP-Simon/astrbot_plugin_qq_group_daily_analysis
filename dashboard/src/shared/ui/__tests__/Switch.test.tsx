import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Switch } from "../switch";

it("开关声明名称与状态，禁用时不修改；不会意外提交外层表单", () => {
  const change = vi.fn();
  const submit = vi.fn((event) => event.preventDefault());
  const view = render(
    <form onSubmit={submit}>
      <Switch aria-label="启用分析" checked={false} onCheckedChange={change} />
    </form>,
  );
  const control = screen.getByRole("switch", { name: "启用分析" });
  expect(control).toHaveAttribute("aria-checked", "false");
  fireEvent.click(control);
  expect(change).toHaveBeenCalledWith(true);
  expect(submit).not.toHaveBeenCalled();
  view.rerender(<Switch aria-label="启用分析" checked disabled onCheckedChange={change} />);
  fireEvent.click(screen.getByRole("switch", { name: "启用分析" }));
  expect(change).toHaveBeenCalledOnce();
  expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
});
