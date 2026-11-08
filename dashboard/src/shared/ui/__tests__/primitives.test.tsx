import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../button";
import {
  Dialog,
  DialogContent,
  DialogClose,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../tabs";
import { NativeSelect } from "../native-select";
import { useState } from "react";

describe("基础控件的交互约定", () => {
  it("受控弹窗没有专用 Trigger 时，也能恢复列表按钮的焦点", async () => {
    function ControlledDialog() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button onClick={() => setOpen(true)}>查看任务</Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent>
              <DialogTitle>任务详情</DialogTitle>
              <DialogDescription>示例任务</DialogDescription>
            </DialogContent>
          </Dialog>
        </>
      );
    }
    render(<ControlledDialog />);
    const trigger = screen.getByRole("button", { name: "查看任务" });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("原生选择器保留表单名称、标签与选项值", () => {
    const change = vi.fn();
    render(
      <label>
        渲染方案
        <NativeSelect name="render" defaultValue="auto" onChange={change}>
          <option value="auto">跟随配置</option>
          <option value="local">本地</option>
        </NativeSelect>
      </label>,
    );
    const select = screen.getByRole("combobox", { name: "渲染方案" });
    fireEvent.change(select, { target: { value: "local" } });
    expect(select).toHaveValue("local");
    expect(select).toHaveAttribute("name", "render");
    expect(change).toHaveBeenCalledTimes(1);
  });
  it("普通按钮不会意外提交表单，禁用后不触发操作", () => {
    const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
    const click = vi.fn();
    const view = render(
      <form onSubmit={submit}>
        <Button onClick={click}>保存</Button>
      </form>,
    );
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(click).toHaveBeenCalledTimes(1);
    expect(submit).not.toHaveBeenCalled();
    view.rerender(
      <Button disabled onClick={click}>
        保存
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("弹窗有名称、支持 Escape，并把焦点交还触发按钮", async () => {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>打开</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>任务信息</DialogTitle>
          <DialogDescription>本次分析的执行信息</DialogDescription>
          <Button>查看记录</Button>
        </DialogContent>
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "打开" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "任务信息" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看记录" })).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("标签页可用键盘切换，内容和选中状态对应", async () => {
    render(
      <Tabs defaultValue="summary">
        <TabsList aria-label="任务信息">
          <TabsTrigger value="summary">摘要</TabsTrigger>
          <TabsTrigger value="logs">日志</TabsTrigger>
        </TabsList>
        <TabsContent value="summary">任务已完成</TabsContent>
        <TabsContent value="logs">日志记录</TabsContent>
      </Tabs>,
    );
    const first = screen.getByRole("tab", { name: "摘要" });
    act(() => first.focus());
    fireEvent.keyDown(first, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByRole("tab", { name: "日志" })).toHaveFocus());
    expect(screen.getByRole("tab", { name: "日志" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("日志记录");
  });
});

it("抽屉可在固定标题中提供唯一关闭入口，沿用焦点恢复", async () => {
  render(
    <Dialog defaultOpen>
      <DialogContent showCloseButton={false}>
        <DialogTitle>分区</DialogTitle>
        <DialogDescription>示例</DialogDescription>
        <DialogClose asChild>
          <Button>关闭分区</Button>
        </DialogClose>
      </DialogContent>
    </Dialog>,
  );
  expect(screen.queryByRole("button", { name: "关闭" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "关闭分区" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});
