import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../../../../shared/api/bridge";
import type { ComicTemplateRotationStatus } from "../../model/comicTemplateRotation";
import { fetchComicRotationStatus, resetComicRotation } from "../comicRotationApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(), apiGet: vi.fn(), apiPost: vi.fn(),
}));

const status: ComicTemplateRotationStatus = {
  mode: "sequential", scope: "global", scope_key: "global", candidates: ["classic", "pixel_rpg"],
  current_template_id: "classic", current_template_name: "原版漫画", next_template_id: "pixel_rpg", next_template_name: "像素 RPG 每日冒险日志", date: "2026-10-17", initialized: true, warning: null,
};

describe("漫画切换进度 API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("解包宿主信封，群查询带完整会话和群号，全局不传群", async () => {
    vi.mocked(apiGet).mockResolvedValue({ data: { status: "ok", data: status } });
    expect(await fetchComicRotationStatus()).toEqual(status);
    expect(apiGet).toHaveBeenLastCalledWith("comic/templates/rotation/status", {});
    await fetchComicRotationStatus("bot:GroupMessage:123");
    expect(apiGet).toHaveBeenLastCalledWith("comic/templates/rotation/status", { group_id: "123", umo: "bot:GroupMessage:123" });
  });

  it("重置明确发送范围，拒绝缺失字段和失败信封", async () => {
    vi.mocked(apiPost).mockResolvedValueOnce({ status: "ok", data: status });
    expect(await resetComicRotation("bot:GroupMessage:123")).toEqual(status);
    expect(apiPost).toHaveBeenCalledWith("comic/templates/rotation/reset", { action: "reset", group_id: "123", umo: "bot:GroupMessage:123" });
    vi.mocked(apiPost).mockResolvedValueOnce({ status: "error", message: "重置被拒绝" });
    await expect(resetComicRotation()).rejects.toThrow("重置被拒绝");
    vi.mocked(apiGet).mockResolvedValueOnce({ data: { mode: "random" } });
    await expect(fetchComicRotationStatus()).rejects.toThrow("未收到有效的漫画模板切换状态");
  });
});
