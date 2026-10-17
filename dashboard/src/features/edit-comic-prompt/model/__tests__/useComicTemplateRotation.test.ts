import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";
import { fetchComicRotationStatus, resetComicRotation } from "../../api/comicRotationApi";
import { DEFAULT_COMIC_TEMPLATE_CANDIDATES, type ComicTemplateRotationStatus } from "../comicTemplateRotation";
import { useComicTemplateRotation } from "../useComicTemplateRotation";

vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));
vi.mock("../../api/comicRotationApi", () => ({ fetchComicRotationStatus: vi.fn(), resetComicRotation: vi.fn() }));
vi.mock("antd", () => ({ message: { success: vi.fn() } }));

const status: ComicTemplateRotationStatus = {
  mode: "sequential", scope: "global", scope_key: "global", candidates: ["classic", "pixel_rpg"], current_template_id: "classic", current_template_name: "原版漫画", next_template_id: "pixel_rpg", next_template_name: "像素 RPG 每日冒险日志", date: "2026-10-17", initialized: true, warning: null,
};
const saved = { comic_template_mode: "sequential", comic_template_scope: "global", comic_template_candidates: ["classic", "pixel_rpg"] };

describe("漫画切换配置与进度交互", () => {
  beforeEach(() => { vi.mocked(fetchDistinctGroups).mockResolvedValue([]); vi.mocked(fetchComicRotationStatus).mockResolvedValue(status); vi.mocked(resetComicRotation).mockResolvedValue({ ...status, initialized: false }); });
  afterEach(() => { vi.resetAllMocks(); vi.useRealTimers(); });

  it("旧配置默认固定模式和全部内置候选，读取状态不会写配置", async () => {
    const onPatch = vi.fn();
    const { result } = renderHook(() => useComicTemplateRotation({ value: {}, savedValue: {}, dirty: false, onPatch }));
    await waitFor(() => expect(result.current.statusLoading).toBe(false));
    expect(result.current.settings).toEqual({ mode: "fixed", scope: "global", candidates: DEFAULT_COMIC_TEMPLATE_CANDIDATES });
    expect(fetchDistinctGroups).not.toHaveBeenCalled();
    expect(fetchComicRotationStatus).toHaveBeenCalledWith(undefined);
    expect(onPatch).not.toHaveBeenCalled();
  });

  it("候选增删保留已有顺序，上下移只回传原始 ID 列表", async () => {
    const onPatch = vi.fn();
    const { result } = renderHook(() => useComicTemplateRotation({ value: saved, savedValue: saved, dirty: false, onPatch }));
    await waitFor(() => expect(result.current.statusLoading).toBe(false));
    act(() => result.current.setCandidates(["scp_dossier", "pixel_rpg", "classic", "custom"]));
    expect(onPatch).toHaveBeenLastCalledWith({ comic_template_candidates: ["classic", "pixel_rpg", "scp_dossier", "custom"] });
    act(() => result.current.moveCandidate("classic", 1));
    expect(onPatch).toHaveBeenLastCalledWith({ comic_template_candidates: ["pixel_rpg", "classic"] });
    onPatch.mockClear();
    act(() => result.current.moveCandidate("classic", -1));
    expect(onPatch).not.toHaveBeenCalled();
  });

  it("群状态用完整 UMO 区分平台，切换群忽略迟到响应，选择不会推进", async () => {
    vi.mocked(fetchDistinctGroups).mockResolvedValue([{ platform: "bot", group_id: "123", group_name: "测试群" }, { platform: "auto", group_id: "456", group_name: "旧占位" }]);
    let finishOld!: (value: ComicTemplateRotationStatus) => void;
    vi.mocked(fetchComicRotationStatus).mockImplementation((umo) => umo === "bot:GroupMessage:123" ? new Promise((resolve) => { finishOld = resolve; }) : Promise.resolve({ ...status, scope: "group", scope_key: umo! }));
    const onPatch = vi.fn();
    const groupConfig = { ...saved, comic_template_scope: "group" };
    const { result } = renderHook(() => useComicTemplateRotation({ value: groupConfig, savedValue: groupConfig, dirty: false, onPatch }));
    await waitFor(() => expect(result.current.options).toHaveLength(1));
    expect(fetchComicRotationStatus).not.toHaveBeenCalled();
    act(() => result.current.setSelectedUmo("bot:GroupMessage:123"));
    act(() => result.current.setSelectedUmo("other:GroupMessage:123"));
    await waitFor(() => expect(result.current.status?.scope_key).toBe("other:GroupMessage:123"));
    await act(async () => finishOld({ ...status, scope_key: "obsolete" }));
    expect(result.current.status?.scope_key).toBe("other:GroupMessage:123");
    expect(onPatch).not.toHaveBeenCalled();
    expect(resetComicRotation).not.toHaveBeenCalled();
  });

  it("有漫画草稿时禁止重置，保存后状态刷新并允许明确重置", async () => {
    const onPatch = vi.fn();
    const { result, rerender } = renderHook(({ value, savedValue, dirty }) => useComicTemplateRotation({ value, savedValue, dirty, onPatch }), { initialProps: { value: saved, savedValue: saved, dirty: true } });
    await waitFor(() => expect(result.current.statusLoading).toBe(false));
    await act(async () => result.current.reset());
    expect(resetComicRotation).not.toHaveBeenCalled();
    const next = { ...saved, comic_template_candidates: ["pixel_rpg", "classic"] };
    rerender({ value: next, savedValue: next, dirty: false });
    await waitFor(() => expect(fetchComicRotationStatus).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(result.current.resetLocked).toBe(false));
    await act(async () => result.current.reset());
    expect(resetComicRotation).toHaveBeenCalledWith(undefined);
    expect(result.current.status?.initialized).toBe(false);
    expect(onPatch).not.toHaveBeenCalled();
  });

  it("状态读取超时后可重试；手动群标识无效时保留当前状态", async () => {
    vi.useFakeTimers();
    vi.mocked(fetchComicRotationStatus).mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(() => useComicTemplateRotation({ value: saved, savedValue: saved, dirty: false, onPatch: vi.fn() }));
    act(() => vi.advanceTimersByTime(15000));
    expect(result.current.statusError).toContain("超时");
    expect(result.current.statusLoading).toBe(false);
    vi.mocked(fetchComicRotationStatus).mockResolvedValue(status);
    await act(async () => result.current.refresh());
    expect(result.current.status).toEqual(status);
    act(() => result.current.setManualUmo("123"));
    act(() => result.current.selectManual());
    expect(result.current.manualError).toContain("完整群会话标识");
    expect(result.current.selectedUmo).toBe("");
  });
});
