import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SearchSelect } from "../search-select";
import { Pagination } from "../pagination";

it("预设入口可使用简短按钮文字，名称仍包含当前选择且保留原始值", () => {
  const change = vi.fn();
  render(
    <SearchSelect
      label="模型预设"
      triggerText="选择预设"
      value="model-a"
      options={[
        { value: "model-a", label: "模型 A" },
        { value: "model-b", label: "模型 B" },
      ]}
      onChange={change}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "模型预设：模型 A" }));
  fireEvent.click(screen.getByRole("button", { name: "模型 B" }));
  expect(change).toHaveBeenCalledWith("model-b");
  expect(screen.getByText("选择预设")).toBeInTheDocument();
});

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

it("大量选项只渲染可见窗口，滚动、搜索和键盘可以访问末尾选项", async () => {
  const change = vi.fn();
  render(
    <SearchSelect
      label="模板"
      value=""
      virtual
      options={Array.from({ length: 500 }, (_, index) => ({
        value: `theme-${index}`,
        label: `模板 ${index}`,
        searchText: `说明 ${index}`,
      }))}
      onChange={change}
    />,
  );
  const trigger = screen.getByRole("button", { name: "模板：请选择" });
  trigger.focus();
  fireEvent.click(trigger);
  expect(screen.getAllByRole("option").length).toBeLessThan(20);
  const viewport = screen.getByRole("listbox").parentElement!;
  fireEvent.scroll(viewport, { target: { scrollTop: 56 * 300 } });
  expect(screen.getByRole("option", { name: "模板 300" })).toHaveAttribute("aria-posinset", "301");
  const search = screen.getByRole("combobox", { name: "搜索模板" });
  fireEvent.keyDown(search, { key: "End" });
  await waitFor(() =>
    expect(
      document.getElementById(search.getAttribute("aria-activedescendant") || ""),
    ).toHaveTextContent("模板 499"),
  );
  expect(screen.getAllByRole("option").length).toBeLessThan(20);
  fireEvent.change(search, { target: { value: "说明 498" } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.keyDown(search, { key: "Enter" });
  expect(change).toHaveBeenCalledWith("theme-498");
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("虚拟选择器关闭后保留当前值，禁用状态禁止继续选择", async () => {
  const options = [
    { value: "one", label: "模板一" },
    { value: "two", label: "模板二" },
  ];
  const change = vi.fn();
  const { rerender } = render(
    <SearchSelect label="模板" value="two" options={options} onChange={change} virtual />,
  );
  const trigger = screen.getByRole("button", { name: "模板：模板二" });
  trigger.focus();
  fireEvent.click(trigger);
  expect(screen.getByRole("option", { name: "模板二" })).toHaveAttribute("aria-selected", "true");
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Home" });
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
  await waitFor(() => expect(trigger).toHaveFocus());
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(trigger);
  rerender(
    <SearchSelect label="模板" value="two" options={options} onChange={change} virtual disabled />,
  );
  expect(screen.getByRole("option", { name: "模板一" })).toBeDisabled();
  fireEvent.click(screen.getByRole("option", { name: "模板一" }));
  expect(change).not.toHaveBeenCalled();
});

it("选项在后台重排时活动项跟随值，移除后不会误选新索引下的另一项", async () => {
  const options = [
    { value: "a", label: "模板甲" },
    { value: "b", label: "模板乙" },
  ];
  const change = vi.fn();
  const view = render(
    <SearchSelect label="模板" value="" options={options} virtual onChange={change} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "模板：请选择" }));
  const input = screen.getByRole("combobox");
  fireEvent.keyDown(input, { key: "End" });
  view.rerender(
    <SearchSelect
      label="模板"
      value=""
      options={[options[1], options[0]]}
      virtual
      onChange={change}
    />,
  );
  fireEvent.keyDown(input, { key: "Enter" });
  expect(change).toHaveBeenCalledWith("b");
  change.mockClear();
  fireEvent.click(screen.getByRole("button", { name: "模板：请选择" }));
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Home" });
  view.rerender(
    <SearchSelect label="模板" value="" options={[options[0]]} virtual onChange={change} />,
  );
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
  expect(change).not.toHaveBeenCalled();
});
