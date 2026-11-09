import { afterEach, expect, it, vi } from "vitest";
import { apiPost } from "@/shared/api/bridge";
import { cancelActiveTask, triggerNewTask } from "@/entities/task/api/taskApi";
import { resumeTraceTask } from "@/entities/trace/api/traceApi";

vi.mock("@/shared/api/bridge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api/bridge")>()),
  apiPost: vi.fn(),
}));
afterEach(() => vi.clearAllMocks());

it.each([null, {}, { status: "ok" }, { status: "ok", data: { trace_id: "" } }])(
  "缺少任务标识不能宣称已提交或已续跑：%j",
  async (response) => {
    vi.mocked(apiPost).mockResolvedValue(response);
    await expect(triggerNewTask("GROUP")).rejects.toThrow("任务");
    await expect(resumeTraceTask("TRACE")).rejects.toThrow("续跑");
  },
);

it.each([0, 1, 2])("任务回执经过 %i 层包装后仍可正确确认", async (layers) => {
  let response: unknown = { trace_id: "TRACE", message: "已排队" };
  for (let depth = 0; depth < layers; depth += 1) response = { status: "ok", data: response };
  vi.mocked(apiPost).mockResolvedValue(response as Awaited<ReturnType<typeof apiPost>>);
  expect(await triggerNewTask("GROUP")).toMatchObject({ status: "ok", trace_id: "TRACE" });
  expect(await resumeTraceTask("TRACE")).toEqual({ trace_id: "TRACE", message: "已排队" });
});

it.each([{}, null, { status: "ok", data: { success: false } }])(
  "取消任务必须收到明确成功回执：%j",
  async (response) => {
    vi.mocked(apiPost).mockResolvedValue(response);
    expect(await cancelActiveTask("TRACE")).toBe(false);
  },
);

it.each([
  { status: "ok", message: "已取消" },
  { status: "ok", data: { success: true } },
])("兼容宿主与 Mock 的取消回执：%j", async (response) => {
  vi.mocked(apiPost).mockResolvedValue(response);
  expect(await cancelActiveTask("TRACE")).toBe(true);
});
