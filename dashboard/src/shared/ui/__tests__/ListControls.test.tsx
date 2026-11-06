import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SearchSelect } from "../search-select";
import { Pagination } from "../pagination";

it("群聊选项支持搜索、选择与关闭焦点恢复，未知选择不被丢弃", async () => {
  const change = vi.fn();
  render(
    <SearchSelect
      label="群聊"
      value="old"
      options={[
        { value: "", label: "全部群聊" },
        { value: "123", label: "摄影群（123）" },
        { value: "456", label: "游戏群（456）" },
      ]}
      onChange={change}
    />,
  );
  const trigger = screen.getByRole("button", { name: "群聊：old" });
  trigger.focus();
  fireEvent.click(trigger);
  fireEvent.change(screen.getByLabelText("搜索群聊"), { target: { value: "摄影" } });
  expect(screen.queryByRole("button", { name: "游戏群（456）" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "摄影群（123）" }));
  expect(change).toHaveBeenCalledWith("123");
  await waitFor(() => expect(trigger).toHaveFocus());
  fireEvent.click(trigger);
  expect(screen.getByLabelText("搜索群聊")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("搜索群聊"), { target: { value: "不存在" } });
  expect(screen.getByRole("status")).toHaveTextContent("没有匹配");
  fireEvent.keyDown(screen.getByLabelText("搜索群聊"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it("分页保留每页数量，边界禁用，修改条数从第一页开始", () => {
  const change = vi.fn();
  const view = render(<Pagination page={1} pageSize={15} total={31} onChange={change} />);
  expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(change).toHaveBeenLastCalledWith(2, 15);
  fireEvent.change(screen.getByLabelText("每页条数"), { target: { value: "50" } });
  expect(change).toHaveBeenLastCalledWith(1, 50);
  view.rerender(<Pagination page={3} pageSize={15} total={31} onChange={change} />);
  expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  view.rerender(<Pagination page={1} pageSize={15} total={0} onChange={change} />);
  expect(screen.getByRole("button", { name: "第 1 页" })).toHaveAttribute("aria-current", "page");
  view.rerender(<Pagination page={1} pageSize={15} total={300} onChange={change} />);
  fireEvent.click(screen.getByRole("button", { name: "第 20 页" }));
  expect(change).toHaveBeenLastCalledWith(20, 15);
});
