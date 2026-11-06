import { expect, it } from "vitest";
import { getRenderAttemptDiagnostic } from "../renderAttempts";

it("只有后续明确成功且为最后一轮时才标记渲染恢复", () => {
  expect(
    getRenderAttemptDiagnostic({
      render_attempts: [{ status: "failed", error: "首次超时" }, { status: "success" }],
    }),
  ).toEqual({ recovered: true, label: "后续渲染已成功", reason: "首次超时" });
  for (const last of [
    { status: "running" },
    { status: "cancelled" },
    {},
    null,
    { status: "success", error: "返回内容无效" },
  ]) {
    expect(
      getRenderAttemptDiagnostic({
        render_attempts: [{ status: "failed" }, { status: "success" }, last],
      })?.recovered,
    ).toBe(false);
  }
});

it("初次成功后失败不称为恢复，缺少失败原因保留轮次", () => {
  expect(
    getRenderAttemptDiagnostic({ render_attempts: [{ status: "success" }, { status: "failed" }] }),
  ).toMatchObject({ recovered: false, reason: "第 2 轮渲染失败，未记录具体原因。" });
  expect(getRenderAttemptDiagnostic({ render_attempts: [{ status: "success" }] })).toBeNull();
  expect(getRenderAttemptDiagnostic({ render_attempts: {} })).toBeNull();
});
