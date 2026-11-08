import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PromptsInspector } from "../PromptsInspector";
import { SpanPayloadViewer } from "../SpanPayloadViewer";
import { copyToClipboard } from "../../../../shared/lib/clipboard";

vi.mock("../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));

it("切换模块与完整重试记录，保留系统提示词、正文和零消耗", async () => {
  render(
    <PromptsInspector
      prompts={{
        topics: {
          system_prompt: "系统指令",
          prompt: "第一轮输入",
          completion: "第一轮输出",
          tokens: 0,
        },
        "topics#schema_retry_1": { prompt: "修复输入一", completion: "未通过格式校验" },
        "topics#schema_retry_2": { provider_id: "backup-model", model: "model" },
        golden_quotes: "金句提示词",
      }}
    />,
  );
  fireEvent.click(screen.getByText("提示词与模型返回 · 2 个模块"));
  expect(screen.getByText("backup-model")).toBeVisible();
  expect(screen.getByText("这次调用未保存提示词或返回正文。")).toBeVisible();
  expect(screen.queryByText("第一轮输入")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("查看记录"), {
    target: { value: "topics#schema_retry_1" },
  });
  expect(screen.getByText("修复输入一")).toBeVisible();
  expect(screen.getByText("未通过格式校验")).toBeVisible();
  expect(screen.queryByText(/有效产物/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("查看记录"), { target: { value: "topics" } });
  expect(screen.getByText("系统指令")).toBeVisible();
  expect(screen.getByText("记录 Tokens").parentElement).toHaveTextContent("0");
  vi.mocked(copyToClipboard).mockResolvedValueOnce(false);
  fireEvent.click(screen.getByRole("button", { name: "复制用户提示词" }));
  expect(await screen.findByRole("status")).toHaveTextContent("复制失败");
  vi.mocked(copyToClipboard).mockResolvedValueOnce(true);
  fireEvent.click(screen.getByRole("button", { name: "复制当前记录" }));
  expect(await screen.findByText("已复制当前记录")).toBeVisible();
  expect(copyToClipboard).toHaveBeenLastCalledWith(
    "=== 系统提示词 ===\n系统指令\n\n=== 用户提示词 ===\n第一轮输入\n\n=== 模型返回 ===\n第一轮输出",
  );
  fireEvent.change(screen.getByLabelText("分析模块"), { target: { value: "golden_quotes" } });
  expect(screen.getByText("金句提示词")).toBeVisible();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("分析模块"), { target: { value: "topics" } });
  expect(screen.getByText("系统指令")).toBeVisible();
});

it("缺失字段不从其他轮次补齐，空响应和无法解析的条目可查看", () => {
  const view = render(
    <PromptsInspector
      prompts={{ topics: { initial_prompt: "首次输入", corrected_completion: "" } }}
    />,
  );
  fireEvent.click(screen.getByText("提示词与模型返回 · 1 个模块"));
  expect(screen.getByText("（空文本）")).toBeVisible();
  expect(screen.queryByRole("region", { name: "用户提示词" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("查看记录"), { target: { value: "topics:initial" } });
  expect(screen.getByText("首次输入")).toBeVisible();
  expect(screen.queryByRole("region", { name: "模型返回" })).not.toBeInTheDocument();
  view.rerender(<PromptsInspector prompts={{ broken: null }} />);
  expect(screen.getByText(/这条记录的格式无法识别/)).toBeVisible();
});

it("原始阶段记录不删减提示词、调用轮次、子任务错误及未知字段", () => {
  const payload = {
    prompts: { topics: "保留全部" },
    llm_attempts: [{ attempt: 1 }],
    render_attempts: [{ custom: true }],
    subtask_errors: [{ area: "话题", error: "失败" }],
    extra: { nested: [1, 2] },
  };
  render(<SpanPayloadViewer payload={payload} />);
  const summary = screen.getByText("原始阶段记录（JSON）");
  fireEvent.click(summary);
  const panel = within(summary.closest("details")!);
  expect(panel.getByText(/保留全部/)).toBeVisible();
  expect(summary.closest("details")?.querySelector("pre")?.textContent).toBe(
    JSON.stringify(payload, null, 2),
  );
});
